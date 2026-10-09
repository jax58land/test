"""複線図ドリルの回路モデル: 単線図データ → 複線図（電線と接続点）の自動生成と論理検証。

単線図は「場所（電源・ジョイントボックス・器具の取付位置）」と「ケーブル」で定義する。
複線図は「ケーブル内の各心線がどの端子/接続点につながるか」の一覧として生成し、
全スイッチの ON/OFF の組合せで点灯をシミュレーションして正しさを確かめる。

回路はすべて本ドリルのオリジナル（試験センター公表の候補問題の図面は転載しない）。
"""
from dataclasses import dataclass, field
from itertools import product

# 心線の色（2心: 黒白 / 3心: 黒白赤）
CORE_COLORS = {2: ["黒", "白"], 3: ["黒", "白", "赤"]}


@dataclass
class Device:
    id: str          # 例 "L-イ", "S-イ", "C1"
    kind: str        # "lamp" | "switch"（片切）| "switch3"（3路）| "outlet" | "pilot"（確認表示灯）
    label: str       # 図に書く記号の文字（イ・ロ など）
    controls: str = ""   # switch/switch3: 点滅させる lamp の label
    first: bool = False  # switch3 のみ: 電源側（0端子に非接地側が来る）なら True
    mode: str = ""       # pilot のみ: "always"（常時点灯）| "same"（同時点滅）| "diff"（異時点滅）


@dataclass
class Location:
    id: str
    kind: str        # "source" | "box" | "device"
    x: float
    y: float
    devices: list = field(default_factory=list)


@dataclass
class Cable:
    a: str           # location id（ボックス側）
    b: str           # location id
    spec: str        # 例 "VVF1.6-2C"
    cores: int


@dataclass
class Problem:
    no: int
    title: str
    note: str
    locations: list
    cables: list

    def loc(self, lid):
        return next(l for l in self.locations if l.id == lid)

    def devices(self):
        return [d for l in self.locations for d in l.devices]


@dataclass
class Wire:
    cable: int       # cables のインデックス
    color: str
    net: str         # 論理ネット名: "N" / "L" / "R-イ"（イの返り線）
    end_a: str       # 端子 or 接続点 例 "B1:N"（ボックス内の接続点）, "L-イ:W"
    end_b: str


# ---------------------------------------------------------------- 生成（7ステップの手順をコード化）
def _device_needs(lb):
    """器具の取付位置 lb へ行くケーブルに必要な心線 [(net, 器具側の端子)]。"""
    need = []
    for d in lb.devices:
        if d.kind == "lamp":
            # 手順2: 接地側（白）はすべての負荷のW端子へ / 手順4: 返り線は非接地側端子へ
            need += [("N", f"{d.id}:W"), (f"R-{d.label}", f"{d.id}:L")]
        elif d.kind == "outlet":
            # 手順3: コンセントは電源に直接（W端子に白）
            need += [("N", f"{d.id}:W"), ("L", f"{d.id}:L")]
    for d in lb.devices:
        if d.kind == "switch3":
            # 3路: 0端子に電源側は非接地側、負荷側は返り線。1・3端子はもう一方の3路と渡り線どうしで結ぶ
            need += [("L" if d.first else f"R-{d.controls}", f"{d.id}:0"),
                     (f"T{d.controls}-1", f"{d.id}:1"), (f"T{d.controls}-3", f"{d.id}:3")]
    sw = [d for d in lb.devices if d.kind == "switch"]
    if sw:
        # 手順3: 非接地側（黒）はスイッチへ。同じ場所に複数ならスイッチ間は渡り線（器具側で共通）
        need.append(("L", "+".join(f"{d.id}:1" for d in sw)))
        # 手順4: 返り線（スイッチ → 電灯）。スイッチ側の心線は黒以外
        need += [(f"R-{d.controls}", f"{d.id}:2") for d in sw]
    for d in lb.devices:
        if d.kind == "pilot":
            # パイロットランプ: 同じ場所のスイッチ（片切）と器具側の渡り線で並べる
            #   常時点灯 = 非接地側と接地側の間 / 同時点滅 = 返り線と接地側の間（電灯と並列）
            #   異時点滅 = 非接地側と返り線の間（スイッチと並列。OFFのとき電灯と直列になって点く）
            a_net, b_net = {"always": ("N", "L"), "same": ("N", f"R-{d.controls}"),
                            "diff": ("L", f"R-{d.controls}")}[d.mode]
            for net, t in ((a_net, "a"), (b_net, "b")):
                i = next((k for k, (n, _) in enumerate(need) if n == net), None)
                if i is None:
                    need.append((net, f"{d.id}:{t}"))
                else:
                    need[i] = (net, need[i][1] + f"+{d.id}:{t}")
    return need


def _downstream(p: Problem, cable):
    """ケーブルの電源から遠い側にある場所 id の集合。"""
    adj = {}
    for c in p.cables:
        if c is not cable:
            adj.setdefault(c.a, []).append(c.b)
            adj.setdefault(c.b, []).append(c.a)
    seen, stack = set(), [cable.b]
    while stack:
        x = stack.pop()
        if x not in seen:
            seen.add(x)
            stack += adj.get(x, [])
    assert "電源" not in seen or cable.b == "電源", f"ケーブルの b 側は電源から遠い側: {cable}"
    return seen


def _net_key(net):
    return ({"N": 0, "L": 1}.get(net, 2), net)


def generate(p: Problem):
    """単線図から複線図の心線リストを作る。ボックスが複数でもよい（ケーブルは木構造・a 側が電源寄りのボックス）。"""
    needs = {l.id: _device_needs(l) for l in p.locations if l.kind == "device"}
    usage = {"N": {"電源"}, "L": {"電源"}}   # net → その net を使う場所
    for lid, need in needs.items():
        for net, _ in need:
            usage.setdefault(net, set()).add(lid)
    wires = []
    for ci, c in enumerate(p.cables):
        la, lb = p.loc(c.a), p.loc(c.b)
        assert la.kind == "box", f"ケーブルの a 側はボックス: {c}"
        colors = list(CORE_COLORS[c.cores])
        box = la.id
        if lb.kind == "source":
            # 手順1: 電源の接地側（白）・非接地側（黒）をボックスへ
            wires += [Wire(ci, "白", "N", f"{box}:N", "電源:N"), Wire(ci, "黒", "L", f"{box}:L", "電源:L")]
            continue
        if lb.kind == "box":
            # ボックス間: 向こう側とこちら側の両方で使う net だけを通す
            sub = _downstream(p, c)
            need = [(net, f"{lb.id}:{net}") for net in sorted(usage, key=_net_key)
                    if usage[net] & sub and usage[net] - sub]
        else:
            need = needs[lb.id]
        assert len(need) == c.cores, f"{lb.id}: 必要な心線 {[n for n, _ in need]} ≠ ケーブル心数 {c.cores}"
        # 手順5: 色決め。N は白、L は黒、返り線・渡り線は残りの色を 黒→白→赤 の順に使う
        for net, term in sorted(need, key=lambda n: {"N": 0, "L": 1}.get(n[0], 2)):
            col = "白" if net == "N" else "黒" if net == "L" else colors[0]
            colors.remove(col)
            wires.append(Wire(ci, col, net, f"{box}:{net}", term))
    return wires


# ---------------------------------------------------------------- 検証
class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def _terms(end):
    return end.split("+")   # 渡り線でまとめた端子


# 電圧計算用の抵抗値[Ω]（100V で 電灯 約100W、パイロットランプは電流がごく小さい）
R_LAMP, R_PILOT, R_LEAK = 100.0, 20000.0, 1e9


def _solve(n, stamps, fixed):
    """節点解析。stamps: [(i, j, R)]、fixed: {i: 電圧}。各節点の電圧のリストを返す。"""
    G = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for i, j, r in stamps:
        g = 1 / r
        G[i][i] += g
        G[j][j] += g
        G[i][j] -= g
        G[j][i] -= g
    for i, v in fixed.items():
        G[i] = [0.0] * n
        G[i][i] = 1.0
        b[i] = v
    for col in range(n):     # ガウスの消去法（部分ピボット）
        piv = max(range(col, n), key=lambda r: abs(G[r][col]))
        G[col], G[piv] = G[piv], G[col]
        b[col], b[piv] = b[piv], b[col]
        for r in range(n):
            if r != col and G[r][col]:
                f = G[r][col] / G[col][col]
                G[r] = [x - f * y for x, y in zip(G[r], G[col])]
                b[r] -= f * b[col]
    return [b[i] / G[i][i] for i in range(n)]


def simulate(p: Problem, wires, state):
    """state: {switch_id: bool}。電灯・パイロットランプを抵抗として各部の電圧を計算し、
    （点灯している電灯 label, 使えるコンセント id, 点灯しているパイロットランプ id）の集合を返す。"""
    uf = _UF()
    for w in wires:
        ts = _terms(w.end_a) + _terms(w.end_b)
        for t in ts[1:]:
            uf.union(ts[0], t)
    for d in p.devices():
        if d.kind == "switch" and state.get(d.id):
            uf.union(f"{d.id}:1", f"{d.id}:2")
        if d.kind == "switch3":   # OFF: 0-1 / ON: 0-3
            uf.union(f"{d.id}:0", f"{d.id}:{3 if state.get(d.id) else 1}")
    L, N = uf.find("電源:L"), uf.find("電源:N")
    assert L != N, "短絡: 電源の L と N がつながっている"
    loads = []   # (device, 端子1, 端子2, R)
    for d in p.devices():
        if d.kind in ("lamp", "outlet"):
            assert uf.find(f"{d.id}:W") != L, f"{d.id}: W端子に非接地側が来ている（極性逆）"
            loads.append((d, f"{d.id}:W", f"{d.id}:L", R_LAMP if d.kind == "lamp" else None))
        elif d.kind == "pilot":
            loads.append((d, f"{d.id}:a", f"{d.id}:b", R_PILOT))
    nodes = {L: 0, N: 1}
    for _, t1, t2, _ in loads:
        for t in (t1, t2):
            nodes.setdefault(uf.find(t), len(nodes))
    stamps = [(nodes[uf.find(t1)], nodes[uf.find(t2)], r) for _, t1, t2, r in loads
              if r and uf.find(t1) != uf.find(t2)]
    stamps += [(i, 1, R_LEAK) for i in range(2, len(nodes))]    # どこにもつながらない節点の電圧を0に寄せる
    v = _solve(len(nodes), stamps, {0: 100.0, 1: 0.0})
    across = lambda t1, t2: abs(v[nodes[uf.find(t1)]] - v[nodes[uf.find(t2)]])
    lit, live, pl = set(), set(), set()
    for d, t1, t2, _ in loads:
        on = across(t1, t2) > 50
        if d.kind == "lamp" and on:
            lit.add(d.label)
        elif d.kind == "outlet" and on and uf.find(t1) == N and uf.find(t2) == L:
            live.add(d.id)
        elif d.kind == "pilot" and on:
            pl.add(d.id)
    return lit, live, pl


def verify(p: Problem, wires):
    """全スイッチ状態で点灯を確認する。
    片切: 電灯イはスイッチイがONのときだけ点く。
    3路: どの状態からでも、同じ組の3路をどちらか1個切り替えると電灯の点滅が反転する（両側から点滅できる）。
    パイロットランプ: 常時点灯=いつも点く / 同時点滅=電灯と同時 / 異時点滅=電灯が消えているときだけ点く。
    コンセントは常に使える。"""
    sws = [d for d in p.devices() if d.kind in ("switch", "switch3")]
    lamps = [d for d in p.devices() if d.kind == "lamp"]
    outlets = [d.id for d in p.devices() if d.kind == "outlet"]
    pilots = [d for d in p.devices() if d.kind == "pilot"]
    three = {lp.label for lp in lamps if any(s.kind == "switch3" and s.controls == lp.label for s in sws)}
    combos = list(product([False, True], repeat=len(sws)))
    result = {}
    for combo in combos:
        state = {s.id: on for s, on in zip(sws, combo)}
        lit, live, pl = simulate(p, wires, state)
        expect = {lp.label for lp in lamps
                  if any(s.kind == "switch" and s.controls == lp.label and state[s.id] for s in sws)}
        assert lit - three == expect, f"{state}: 点灯 {lit - three} ≠ 期待 {expect}"
        assert live == set(outlets), f"{state}: コンセント {live} ≠ {outlets}"
        for d in pilots:
            want = {"always": True, "same": d.controls in lit, "diff": d.controls not in lit}[d.mode]
            assert (d.id in pl) == want, f"{state}: パイロットランプ{d.id}（{d.mode}）の点灯が違う"
        result[combo] = lit
    for label in three:
        assert any(label in lit for lit in result.values()), f"電灯{label}が一度も点かない"
        for combo, lit in result.items():
            for i, s in enumerate(sws):
                if s.kind == "switch3" and s.controls == label:
                    flipped = tuple(not v if j == i else v for j, v in enumerate(combo))
                    assert (label in lit) != (label in result[flipped]), \
                        f"3路{s.id}を切り替えても電灯{label}が変わらない: {combo}"
    # 色のルール: 接地側（N）はすべて白。白が N 以外に使われるのはスイッチ行きのケーブルだけ
    for w in wires:
        c = p.cables[w.cable]
        if w.net == "N":
            assert w.color == "白", f"接地側が白でない: {w}"
        elif w.color == "白":
            assert any(d.kind in ("switch", "switch3") for d in p.loc(c.b).devices), f"白を非接地側に使用: {w}"
        # 器具のW端子には必ず白
        for t in _terms(w.end_b):
            if t.endswith(":W"):
                assert w.color == "白", f"W端子に白以外: {w}"
    # 心数とケーブルの対応
    for ci, c in enumerate(p.cables):
        cols = sorted(w.color for w in wires if w.cable == ci)
        assert cols == sorted(CORE_COLORS[c.cores]), f"ケーブル{ci} {c.spec}: 心線 {cols}"
    return len(combos)


def box_joints(p: Problem, wires):
    """ボックス内の接続点ごとに、つながる心線の色を返す（スリーブ/コネクタ選定の下書き）。"""
    boxes = {l.id for l in p.locations if l.kind == "box"}
    joints = {}
    for w in wires:
        for end in (w.end_a, w.end_b):
            if end.split(":")[0] in boxes:
                joints.setdefault(end, []).append(w.color)
    return joints


# ---------------------------------------------------------------- リングスリーブ（未確認のため非表示）
# 1.6mm 電線だけの接続点: 本数 → (スリーブの大きさ, 圧着マーク)。
# 出典の原文が未確認（docs/research/2026-10-10-exam-and-sleeve.md）。確認できるまで PDF には載せない。
SHOW_SLEEVE = False
SLEEVE_16 = {2: ("小", "○"), 3: ("小", "小"), 4: ("小", "小"), 5: ("中", "中"), 6: ("中", "中"), 7: ("大", "大")}


def sleeve(n_16):
    """1.6mm の電線 n_16 本をつなぐときの (スリーブ, 圧着マーク)。表にない本数は None。"""
    return SLEEVE_16.get(n_16)


# ---------------------------------------------------------------- 問題データ
def _dev(*a, **k):
    return Device(*a, **k)


PROBLEMS = [
    Problem(
        1, "電灯1灯＋片切スイッチ＋コンセント",
        "いちばん基本の形。接地側（白）がどこへ行くかだけを追いかける。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 90, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 90, 45, [_dev("S-イ", "switch", "イ", controls="イ")]),
            Location("P3", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-2C", 2),
            Cable("B1", "P3", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        2, "電灯2灯＋片切スイッチ2個（同じ場所）＋コンセント",
        "スイッチが2個並ぶと、非接地側（黒）は1本だけ来て器具側で渡り線にする。返り線は2本で3心ケーブル。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 55, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 125, 165, [_dev("L-ロ", "lamp", "ロ")]),
            Location("P3", "device", 90, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("S-ロ", "switch", "ロ", controls="ロ")]),
            Location("P4", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-2C", 2),
            Cable("B1", "P3", "VVF1.6-3C", 3),
            Cable("B1", "P4", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        3, "電灯1灯を2か所から点滅（3路スイッチ）＋コンセント",
        "3路の0端子には「電源側は黒（非接地側）」「電灯側は返り線」。1と3はスイッチどうしを渡り線で結ぶだけ。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 90, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 50, 45, [_dev("S3-A", "switch3", "イ", controls="イ", first=True)]),
            Location("P3", "device", 135, 45, [_dev("S3-B", "switch3", "イ", controls="イ")]),
            Location("P4", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-3C", 3),
            Cable("B1", "P3", "VVF1.6-3C", 3),
            Cable("B1", "P4", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        4, "パイロットランプ 異時点滅（スイッチの位置表示）",
        "異時点滅はスイッチと並列。電灯が消えているときだけ、電灯と直列に小さな電流が流れて点く。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 90, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 90, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("PL1", "pilot", "", controls="イ", mode="diff")]),
            Location("P3", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-2C", 2),
            Cable("B1", "P3", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        5, "パイロットランプ 同時点滅（換気扇などの消し忘れ防止）",
        "同時点滅は電灯と並列（返り線と接地側の間）。スイッチの場所まで白が要るので3心になる。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 90, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 90, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("PL1", "pilot", "", controls="イ", mode="same")]),
            Location("P3", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-3C", 3),
            Cable("B1", "P3", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        6, "パイロットランプ 常時点灯（電源が来ていることの表示）",
        "常時点灯は非接地側と接地側の間。スイッチとは無関係に点きっぱなし。スイッチ行きは黒・白・赤の3心。",
        [
            Location("電源", "source", 20, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 90, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 90, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("PL1", "pilot", "", mode="always")]),
            Location("P3", "device", 160, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-3C", 3),
            Cable("B1", "P3", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        7, "ボックス2個：スイッチ2個を1か所にまとめる",
        "ボックス間を通るのは「向こう側でも使う線」だけ。ここでは白・黒とロの返り線（赤）の3本。",
        [
            Location("電源", "source", 15, 110),
            Location("B1", "box", 65, 110),
            Location("B2", "box", 130, 110),
            Location("P1", "device", 65, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 65, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("S-ロ", "switch", "ロ", controls="ロ")]),
            Location("P3", "device", 130, 165, [_dev("L-ロ", "lamp", "ロ")]),
            Location("P4", "device", 175, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-3C", 3),
            Cable("B1", "B2", "VVF1.6-3C", 3),
            Cable("B2", "P3", "VVF1.6-2C", 2),
            Cable("B2", "P4", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        8, "ボックス2個：3路スイッチをボックスごとに分ける",
        "3路の渡り線2本はボックス間も通す。非接地側（L）はB2で使わないので、ボックス間を通らない。",
        [
            Location("電源", "source", 15, 110),
            Location("B1", "box", 65, 110),
            Location("B2", "box", 130, 110),
            Location("P1", "device", 65, 45, [_dev("S3-A", "switch3", "イ", controls="イ", first=True)]),
            Location("P2", "device", 65, 165, [_dev("C1", "outlet", "")]),
            Location("P3", "device", 130, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P4", "device", 130, 45, [_dev("S3-B", "switch3", "イ", controls="イ")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-3C", 3),
            Cable("B1", "P2", "VVF1.6-2C", 2),
            Cable("B1", "B2", "VVF1.6-3C", 3),
            Cable("B2", "P3", "VVF1.6-2C", 2),
            Cable("B2", "P4", "VVF1.6-3C", 3),
        ],
    ),
    Problem(
        9, "ボックス2個：同時点滅のパイロットランプ",
        "PLの返り線は電灯までそのまま延びる。ボックス間は白・黒・赤で、赤がイの返り線。",
        [
            Location("電源", "source", 15, 110),
            Location("B1", "box", 65, 110),
            Location("B2", "box", 130, 110),
            Location("P1", "device", 65, 165, [_dev("C1", "outlet", "")]),
            Location("P2", "device", 65, 45, [_dev("S-イ", "switch", "イ", controls="イ"),
                                              _dev("PL1", "pilot", "", controls="イ", mode="same")]),
            Location("P3", "device", 130, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P4", "device", 130, 45, [_dev("S-ロ", "switch", "ロ", controls="ロ")]),
            Location("P5", "device", 175, 110, [_dev("L-ロ", "lamp", "ロ")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-3C", 3),
            Cable("B1", "B2", "VVF1.6-3C", 3),
            Cable("B2", "P3", "VVF1.6-2C", 2),
            Cable("B2", "P4", "VVF1.6-2C", 2),
            Cable("B2", "P5", "VVF1.6-2C", 2),
        ],
    ),
    Problem(
        10, "総合：3路＋片切＋異時点滅＋コンセント",
        "部品が増えても手順は同じ。白→黒→返り線→渡り線の順に1本ずつ書き足す。",
        [
            Location("電源", "source", 15, 110),
            Location("B1", "box", 90, 110),
            Location("P1", "device", 55, 165, [_dev("L-イ", "lamp", "イ")]),
            Location("P2", "device", 125, 165, [_dev("L-ロ", "lamp", "ロ")]),
            Location("P3", "device", 40, 45, [_dev("S3-A", "switch3", "イ", controls="イ", first=True)]),
            Location("P4", "device", 90, 45, [_dev("S3-B", "switch3", "イ", controls="イ")]),
            Location("P5", "device", 145, 45, [_dev("S-ロ", "switch", "ロ", controls="ロ"),
                                               _dev("PL1", "pilot", "", controls="ロ", mode="diff")]),
            Location("P6", "device", 170, 110, [_dev("C1", "outlet", "")]),
        ],
        [
            Cable("B1", "電源", "VVF1.6-2C", 2),
            Cable("B1", "P1", "VVF1.6-2C", 2),
            Cable("B1", "P2", "VVF1.6-2C", 2),
            Cable("B1", "P3", "VVF1.6-3C", 3),
            Cable("B1", "P4", "VVF1.6-3C", 3),
            Cable("B1", "P5", "VVF1.6-2C", 2),
            Cable("B1", "P6", "VVF1.6-2C", 2),
        ],
    ),
]
