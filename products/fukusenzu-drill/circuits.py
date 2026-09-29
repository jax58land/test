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
    kind: str        # "lamp" | "switch"（片切）| "switch3"（3路）| "outlet"
    label: str       # 図に書く記号の文字（イ・ロ など）
    controls: str = ""   # switch/switch3: 点滅させる lamp の label
    first: bool = False  # switch3 のみ: 電源側（0端子に非接地側が来る）なら True


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
def generate(p: Problem):
    """単線図から複線図の心線リストを作る。ボックス1個・器具はボックスから直接配線される前提（v0）。"""
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
        need = []   # (net, 器具側の端子)
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
        assert len(need) == c.cores, f"{lb.id}: 必要な心線 {len(need)} ≠ ケーブル心数 {c.cores}"
        # 手順5: 色決め。N は白、L は黒、返り線は残りの色を 黒→白→赤 の順に使う
        order = sorted(need, key=lambda n: {"N": 0, "L": 1}.get(n[0], 2))
        for net, term in order:
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


def simulate(p: Problem, wires, state):
    """state: {switch_id: bool}。点灯している lamp label の集合と、使えるコンセント id の集合を返す。"""
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
    lit, live = set(), set()
    for d in p.devices():
        if d.kind in ("lamp", "outlet"):
            w, l = uf.find(f"{d.id}:W"), uf.find(f"{d.id}:L")
            if w == N and l == L:
                (lit if d.kind == "lamp" else live).add(d.label if d.kind == "lamp" else d.id)
            assert not (w == L and l == N), f"{d.id}: W端子に非接地側が来ている（極性逆）"
    return lit, live


def verify(p: Problem, wires):
    """全スイッチ状態で点灯を確認する。
    片切: 電灯イはスイッチイがONのときだけ点く。
    3路: どの状態からでも、同じ組の3路をどちらか1個切り替えると電灯の点滅が反転する（両側から点滅できる）。
    コンセントは常に使える。"""
    sws = [d for d in p.devices() if d.kind in ("switch", "switch3")]
    lamps = [d for d in p.devices() if d.kind == "lamp"]
    outlets = [d.id for d in p.devices() if d.kind == "outlet"]
    three = {lp.label for lp in lamps if any(s.kind == "switch3" and s.controls == lp.label for s in sws)}
    combos = list(product([False, True], repeat=len(sws)))
    result = {}
    for combo in combos:
        state = {s.id: on for s, on in zip(sws, combo)}
        lit, live = simulate(p, wires, state)
        expect = {lp.label for lp in lamps
                  if any(s.kind == "switch" and s.controls == lp.label and state[s.id] for s in sws)}
        assert lit - three == expect, f"{state}: 点灯 {lit - three} ≠ 期待 {expect}"
        assert live == set(outlets), f"{state}: コンセント {live} ≠ {outlets}"
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
    joints = {}
    for w in wires:
        if ":" in w.end_a and p.loc(w.end_a.split(":")[0]).kind == "box":
            joints.setdefault(w.end_a, []).append(w.color)
    return joints


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
]
