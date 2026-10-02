"""複線図ドリルの検証: 全問題の自動生成結果が点灯シミュレーションと色ルールを通り、
わざと壊した配線はきちんと検出されること。最後に PDF を生成して中身を確認する。

usage: python test_build.py
"""
import copy
import re
from pathlib import Path

from build import DISCLAIMER, main
from circuits import PROBLEMS, generate, verify


def must_fail(p, wires, why):
    try:
        verify(p, wires)
    except AssertionError:
        return
    raise AssertionError(f"誤配線を検出できない: {why}")


def test_all_problems_verify():
    for p in PROBLEMS:
        assert verify(p, generate(p)) == 2 ** sum(d.kind in ("switch", "switch3") for d in p.devices())


def test_problem1_expected_wiring():
    w = {(x.end_b, x.color) for x in generate(PROBLEMS[0])}
    assert ("L-イ:W", "白") in w and ("L-イ:L", "黒") in w
    assert ("S-イ:1", "黒") in w and ("S-イ:2", "白") in w     # スイッチは非接地側（黒）から
    assert ("C1:W", "白") in w and ("C1:L", "黒") in w


def test_problem2_three_core_and_jumper():
    w = generate(PROBLEMS[1])
    three = [x for x in w if PROBLEMS[1].cables[x.cable].cores == 3]
    assert sorted(x.color for x in three) == ["白", "赤", "黒"]
    assert any(x.end_b == "S-イ:1+S-ロ:1" and x.color == "黒" for x in three)   # 渡り線


def test_detects_broken_wiring():
    for p in PROBLEMS:
        base = generate(p)
        # 1) 電灯の返り線を別の電灯へ（イとロの取り違え / 1灯なら電源直結）
        w = copy.deepcopy(base)
        r = next(x for x in w if x.end_b.startswith("L-") and x.end_b.endswith(":L"))
        r.end_a = r.end_a.split(":")[0] + ":L"
        must_fail(p, w, "電灯が常時点灯")
        # 2) スイッチを接地側に入れる
        w = copy.deepcopy(base)
        s = next(x for x in w if x.net == "L" and x.end_b.startswith("S"))
        s.end_a = s.end_a.split(":")[0] + ":N"
        must_fail(p, w, "スイッチが接地側")
        # 3) 電灯のW端子に黒
        w = copy.deepcopy(base)
        a = next(x for x in w if x.end_b.endswith(":W") and x.end_b.startswith("L-"))
        b = next(x for x in w if x.cable == a.cable and x is not a)
        a.color, b.color = b.color, a.color
        must_fail(p, w, "W端子の色違い")
        # 4) コンセントの極性逆
        w = copy.deepcopy(base)
        cw = next(x for x in w if x.end_b.startswith("C") and x.end_b.endswith(":W"))
        cl = next(x for x in w if x.end_b.startswith("C") and x.end_b.endswith(":L"))
        cw.end_a, cl.end_a = cl.end_a, cw.end_a
        must_fail(p, w, "コンセント極性")


def test_problem3_three_way():
    p = PROBLEMS[2]
    w = generate(p)
    ends = {(x.end_b, x.color) for x in w}
    assert ("S3-A:0", "黒") in ends and ("S3-B:0", "黒") in ends   # 0端子: 電源側は非接地側、負荷側は返り線
    for sid in ("S3-A", "S3-B"):
        assert (f"{sid}:1", "白") in ends and (f"{sid}:3", "赤") in ends
    assert verify(p, w) == 4
    # 渡り線の片方を返り線側（0端子）につなぐと、片側から点滅できなくなる
    bad = copy.deepcopy(w)
    t1 = next(x for x in bad if x.end_b == "S3-B:1")
    t1.end_a = "B1:R-イ"
    must_fail(p, bad, "3路の渡り線ミス")
    # 電源側と負荷側の3路の0端子を入れ替え（どちらも非接地側）→ 電灯が点かない/短絡
    bad = copy.deepcopy(w)
    r = next(x for x in bad if x.end_b == "S3-B:0")
    r.end_a = "B1:L"
    must_fail(p, bad, "3路の0端子ミス")


def test_pilot_lamps():
    from circuits import simulate
    by_no = {p.no: p for p in PROBLEMS}
    # 異時点滅: OFFでPLだけ点く（電灯と直列でも電灯は点かない）、ONで電灯だけ点く
    p = by_no[4]
    w = generate(p)
    assert simulate(p, w, {"S-イ": False}) == (set(), {"C1"}, {"PL1"})
    assert simulate(p, w, {"S-イ": True}) == ({"イ"}, {"C1"}, set())
    assert all(p.cables[x.cable].cores == 2 for x in w if p.cables[x.cable].b == "P2")   # スイッチ行きは2心
    # 同時点滅・常時点灯はスイッチ行きが3心で、白（接地側）がPLへ行く
    for no in (5, 6):
        p = by_no[no]
        w = generate(p)
        assert any(x.color == "白" and x.net == "N" and "PL1:a" in x.end_b for x in w)
    # 取り違え: 同時点滅の配線を「異時点滅」として、常時点灯の配線を「同時点滅」として検査すると不合格になる
    p = copy.deepcopy(by_no[5])
    next(d for d in p.devices() if d.kind == "pilot").mode = "diff"
    must_fail(p, generate(by_no[5]), "同時点滅の配線を異時点滅として検査")
    p = copy.deepcopy(by_no[6])
    next(d for d in p.devices() if d.kind == "pilot").mode = "same"
    must_fail(p, generate(by_no[6]), "常時点灯の配線を同時点滅として検査")


def test_two_boxes():
    from circuits import box_joints
    by_no = {p.no: p for p in PROBLEMS}
    # 問題7: ボックス間は N・L・ロの返り線の3本。イの返り線はB1の中だけで完結する
    p = by_no[7]
    w = generate(p)
    between = {x.net: x.color for x in w if p.cables[x.cable].b == "B2"}
    assert between == {"N": "白", "L": "黒", "R-ロ": "赤"}
    assert "B2:R-イ" not in box_joints(p, w)
    # 問題8: ボックス間は N と3路の渡り線2本。L は通らない
    p = by_no[8]
    w = generate(p)
    between = {x.net for x in w if p.cables[x.cable].b == "B2"}
    assert between == {"N", "Tイ-1", "Tイ-3"}
    # 誤配線: ボックス間の渡り線を入れ替えても3路は動く（流儀の違い）が、渡り線を N につなぐと検出される
    bad = copy.deepcopy(w)
    x = next(x for x in bad if p.cables[x.cable].b == "B2" and x.net == "Tイ-1")
    x.end_b = "B2:N"
    must_fail(p, bad, "ボックス間の渡り線を接地側へ")


def test_page_text_fits():
    from circuits import box_joints
    for p in PROBLEMS:
        assert len(p.note) <= 60, f"問題{p.no}の説明が長すぎて1行に収まらない"
        n = len(box_joints(p, generate(p)))
        assert n <= (8 if sum(l.kind == "box" for l in p.locations) > 1 else 6), f"問題{p.no}: 接続点の表が入らない"


def test_routing_no_overlap():
    """色（net）の違う心線どうしが、同じ線上で重ならないこと（交差はよい）。"""
    from reportlab.lib.units import mm
    from build import junction_xy, route_wires
    for p in PROBLEMS:
        w = generate(p)
        P = lambda l: (l.x * mm, l.y * mm)
        jxy, radius = junction_xy(p, w, P)
        segs = []
        for wire, pts in route_wires(p, w, P, jxy, radius):
            for a, b in zip(pts, pts[1:]):
                if abs(a[0] - b[0]) > 1e-6 or abs(a[1] - b[1]) > 1e-6:
                    segs.append((wire.net, a, b))
        for i, (n1, a1, b1) in enumerate(segs):
            for n2, a2, b2 in segs[i + 1:]:
                if n1 == n2:
                    continue
                for ax in (0, 1):          # 0: 縦線（x 一定） / 1: 横線（y 一定）
                    if all(abs(q[ax] - a1[ax]) < 1e-6 for q in (b1, a2, b2)):
                        o = 1 - ax
                        lo = max(min(a1[o], b1[o]), min(a2[o], b2[o]))
                        hi = min(max(a1[o], b1[o]), max(a2[o], b2[o]))
                        assert hi - lo < 1e-6, f"問題{p.no}: {n1} と {n2} の線が重なっている"


def test_pdf(tmp=Path(__file__).resolve().parent / "_test.pdf"):
    out = main(tmp)
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    assert pages == 1 + len(PROBLEMS), pages
    assert "有資格者" in DISCLAIMER
    out.unlink()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL PASSED")
