"""单个赘余标记修复：穷举/随机对拍、锁定保护、删位裁决与偶数一致性。"""

from __future__ import annotations

import itertools
import random
import time

import pytest

from app.repair import OPEN_TO_CLOSE, repair, repair_redundant
from tests.brute import brute_force_redundant_plans

CHARS = "()[]{}"


def run(s, locked=None, check_ambiguity=False):
    n = len(s)
    locked = locked if locked is not None else [False] * n
    return repair_redundant(
        list(s), list(locked), check_ambiguity=check_ambiguity
    )


def check_case(chars, locked):
    n = len(chars)
    expected_plans = brute_force_redundant_plans(chars, locked)
    got = repair_redundant(chars, locked)
    ambiguous = repair_redundant(chars, locked, check_ambiguity=True)
    if not expected_plans:
        assert got is None, f"{chars=} {locked=} 应无解，DP 给出 {got}"
        assert ambiguous is None, f"{chars=} {locked=} 应无解，歧义核查伪造备选"
        return
    exp_cost, exp_text, exp_del_raw = expected_plans[0]
    exp_del = exp_del_raw if exp_del_raw >= 0 else None
    assert got is not None, f"{chars=} {locked=} 应有解 {exp_text}，DP 返回 None"
    text, pairs, deleted = got
    assert text == exp_text, (
        f"{''.join(chars)} {locked=} DP={text} 暴力={exp_text}"
    )
    assert deleted == exp_del, (
        f"{''.join(chars)} {locked=} DP 删位={deleted} 暴力={exp_del}"
    )
    # 奇数长度必须删除恰好一个位置；偶数长度不删
    assert (deleted is not None) == (n % 2 == 1)

    kept = [i for i in range(n) if i != deleted]
    assert len(text) == len(kept)
    # 总修改数一致：删除计 1 次，替换逐位核对
    repl = sum(chars[i] != text[p] for p, i in enumerate(kept))
    assert repl + (deleted is not None) == exp_cost
    # 锁定保护：锁定位置既不可被删除也不可被替换
    if deleted is not None:
        assert not locked[deleted], "锁定位置被删除"
    for p, i in enumerate(kept):
        if locked[i]:
            assert text[p] == chars[i], "锁定位置被替换"
    # pairs：原稿坐标、与修复串栈式扫描一致、恰好覆盖全部未删位置
    stack = []
    derived = []
    for idx, ch in enumerate(text):
        if ch in OPEN_TO_CLOSE:
            stack.append(idx)
        else:
            assert stack, "闭括号多于开括号"
            o = stack.pop()
            assert OPEN_TO_CLOSE[text[o]] == ch, "括号类型不匹配"
            derived.append([kept[o], kept[idx]])
    assert not stack
    assert pairs == sorted(derived)
    assert sorted(p for pair in pairs for p in pair) == kept

    first_text, first_pairs, first_deleted, plans = ambiguous
    assert first_text == text
    assert first_pairs == pairs
    assert first_deleted == deleted
    assert len(plans) == len(expected_plans)
    assert [
        (plan["repaired"], plan["deleted_index"]) for plan in plans
    ] == [
        (plan_text, plan_del if plan_del >= 0 else None)
        for _, plan_text, plan_del in expected_plans
    ]
    assert all(plan["cost"] == exp_cost for plan in plans)
    assert len({
        (plan["repaired"], plan["deleted_index"]) for plan in plans
    }) == len(plans)
    for plan, (plan_cost, plan_text, plan_del_raw) in zip(
        plans, expected_plans
    ):
        plan_del = plan_del_raw if plan_del_raw >= 0 else None
        assert plan["repaired"] == plan_text
        assert plan["cost"] == plan_cost
        assert plan["deleted_index"] == plan_del
        if plan_del is not None:
            assert not locked[plan_del]
        plan_kept = [i for i in range(n) if i != plan_del]
        stack = []
        derived = []
        for idx, ch in enumerate(plan_text):
            if ch in OPEN_TO_CLOSE:
                stack.append(idx)
            else:
                o = stack.pop()
                assert OPEN_TO_CLOSE[plan_text[o]] == ch
                derived.append([plan_kept[o], plan_kept[idx]])
        assert not stack
        assert plan["pairs"] == sorted(derived)
        assert sorted(p for pair in plan["pairs"] for p in pair) == plan_kept
        for p, i in enumerate(plan_kept):
            if locked[i]:
                assert plan_text[p] == chars[i]


@pytest.mark.parametrize("n", [3, 4])
def test_exhaustive(n):
    """n=3: 1728 种输入全枚举（奇数，必删一位）；n=4: 20736 种（偶数）。"""
    for chars in itertools.product(CHARS, repeat=n):
        for locked in itertools.product([False, True], repeat=n):
            check_case(list(chars), list(locked))


@pytest.mark.parametrize("n,samples", [(5, 2000), (6, 1500), (7, 1000), (8, 800)])
def test_random_sample(n, samples):
    rng = random.Random(20260925 + n)
    for _ in range(samples):
        chars = [rng.choice(CHARS) for _ in range(n)]
        locked = [rng.random() < 0.4 for _ in range(n)]
        check_case(chars, locked)


def test_random_biased_locked():
    """高锁定率随机样例，制造更多无可删位与受限情形。"""
    rng = random.Random(11)
    for _ in range(1000):
        n = rng.randint(3, 8)
        chars = [rng.choice(CHARS) for _ in range(n)]
        locked = [rng.random() < 0.75 for _ in range(n)]
        check_case(chars, locked)


@pytest.mark.parametrize("n,samples", [(4, 200), (6, 200), (8, 100), (20, 30), (80, 5)])
def test_even_length_matches_original_repairer(n, samples):
    """偶数长度无需删除：结果必须与 repair() 完全一致，删位为 None。"""
    rng = random.Random(900 + n)
    for _ in range(samples):
        chars = [rng.choice(CHARS) for _ in range(n)]
        locked = [rng.random() < 0.4 for _ in range(n)]
        expected = repair(chars, locked)
        got = repair_redundant(chars, locked)
        if expected is None:
            assert got is None
            continue
        text, pairs, deleted = got
        assert deleted is None
        assert (text, pairs) == expected


class TestDeleteTieBreaking:
    def test_same_text_smaller_deleted_index(self):
        # "(()"：删 0 或删 1 都得 "()" 且同改 1 次，取下标更小者；
        # 删的是下标 0，配对回指原稿下标 1、2
        assert run("(()") == ("()", [[1, 2]], 0)

    def test_same_text_smaller_deleted_index_shifted(self):
        # "())"：删 1 或删 2 都得 "()"，取 1；pairs 回指原稿坐标
        assert run("())") == ("()", [[0, 2]], 1)

    def test_text_beats_deleted_index(self):
        # "})()("：删 1 得 "{()}"、删 4 得 "()()"，同改 2 次；
        # "()()" 字典序更小，即使删位更大也取它
        assert run("})()(") == ("()()", [[0, 1], [2, 3]], 4)

    def test_all_same_chars(self):
        # "((("：删哪位都得 "((" 再改 1 次成 "()"，取最小删位 0；
        # 配对回指原稿下标 1、2
        assert run("(((") == ("()", [[1, 2]], 0)

    def test_locked_forces_later_delete(self):
        # 首位锁定：最优删位 0 不可用，退而删 1
        assert run("(()", [True, False, False]) == ("()", [[0, 2]], 1)


class TestLockedProtection:
    def test_locked_position_not_deleted(self):
        # "())" 未锁定时最优删位为 1；锁定下标 1 后只能改删 2
        assert run("())") == ("()", [[0, 2]], 1)
        assert run("())", [False, True, False]) == ("()", [[0, 1]], 2)

    def test_locked_surplus_no_repair(self):
        # 赘余位被锁定且剩余位置无法补救 => NO_REPAIR
        assert run("()(", [False, False, True]) is None

    def test_all_locked_odd_no_repair(self):
        # 奇数长度全锁定：无可删位，NO_REPAIR，不得伪造部分配对
        assert run("(()", [True] * 3) is None
        assert run("())", [True] * 3) is None
        assert run("(((", [True] * 3) is None

    def test_locked_survivors_unfixable_no_repair(self):
        # 删除唯一的未锁定位置后，剩下的全锁定串仍不合法
        assert run("(((", [True, False, True]) is None

    def test_locked_positions_untouched(self):
        s = "({[}]"
        locked = [True, False, True, False, False]
        text, pairs, deleted = run(s, locked)
        assert deleted is None or not locked[deleted]
        kept = [i for i in range(len(s)) if i != deleted]
        for p, i in enumerate(kept):
            if locked[i]:
                assert text[p] == s[i]
        # 可逐位置核验的完整结构（原稿坐标）
        assert sorted(p for pair in pairs for p in pair) == kept


class TestNoRepair:
    def test_even_unfixable_stays_no_repair(self):
        # 偶数长度删除无济于事，与原修复器一致返回 None
        assert run("((", [True, True]) is None
        assert run("([)]", [True] * 4) is None

    def test_even_valid_zero_cost_no_deletion(self):
        # 偶数长度已合法：零修改，不删除
        assert run("()()", [True] * 4) == ("()()", [[0, 1], [2, 3]], None)
        assert run("()()") == ("()()", [[0, 1], [2, 3]], None)


class TestAmbiguity:
    def test_same_text_different_deleted_positions_are_distinct(self):
        # 结果同为 "()"，删 0 与删 1 是两个互异方案；必须保留原稿删位
        _, _, _, plans = run("(()", check_ambiguity=True)
        assert plans == [
            {
                "cost": 1,
                "repaired": "()",
                "pairs": [[1, 2]],
                "deleted_index": 0,
            },
            {
                "cost": 1,
                "repaired": "()",
                "pairs": [[0, 2]],
                "deleted_index": 1,
            },
        ]

    def test_same_text_replacement_coordinates_follow_deleted_position(self):
        # "((("：删 0 时替换原稿 1；删 1 时替换原稿 2，配对坐标也不同
        _, _, _, plans = run("(((", check_ambiguity=True)
        assert plans[0]["deleted_index"] == 0
        assert plans[0]["pairs"] == [[1, 2]]
        assert plans[1]["deleted_index"] == 1
        assert plans[1]["pairs"] == [[0, 2]]
        assert all(plan["repaired"] == "()" for plan in plans)
        assert all(plan["cost"] == 2 for plan in plans)

    def test_text_order_before_delete_index(self):
        _, _, _, plans = run("})()(", check_ambiguity=True)
        assert [(p["repaired"], p["deleted_index"]) for p in plans][0] == (
            "()()",
            4,
        )

    def test_locked_conflict_makes_delete_alternative_unavailable(self):
        # 首删位锁定后，同串备选只剩删除下标 1；不能伪造锁定删位方案
        _, _, _, plans = run(
            "(()", [True, False, False], check_ambiguity=True
        )
        assert [plan["deleted_index"] for plan in plans] == [1]

    def test_unique_no_deletion_for_even_valid(self):
        _, _, deleted, plans = run(
            "()()", [True] * 4, check_ambiguity=True
        )
        assert deleted is None
        assert len(plans) == 1
        assert plans[0] == {
            "cost": 0,
            "repaired": "()()",
            "pairs": [[0, 1], [2, 3]],
            "deleted_index": None,
        }

    def test_no_repair_has_no_alternative(self):
        assert run("(((", [True] * 3, check_ambiguity=True) is None


class TestPerformance:
    def test_max_length_random(self):
        rng = random.Random(81)
        chars = [rng.choice(CHARS) for _ in range(81)]
        locked = [rng.random() < 0.3 for _ in range(81)]
        t0 = time.perf_counter()
        out = repair_redundant(chars, locked)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0
        assert out is not None
        text, pairs, deleted = out
        assert len(text) == 80
        assert len(pairs) == 40
        assert deleted is not None
