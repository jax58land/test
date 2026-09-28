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
        assert verify(p, generate(p)) == 2 ** sum(d.kind == "switch" for d in p.devices())


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
        s = next(x for x in w if x.end_b.startswith("S-") and ":1" in x.end_b)
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
