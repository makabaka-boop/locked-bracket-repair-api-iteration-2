"""歧义核查：最小修改数下的前两个互异方案与"唯一／存在备选"结论。

- 短串穷举（替换与删除都穷举）与随机样例，对拍暴力枚举器
  （tests/brute.py 的 brute_force_top2 / brute_force_redundant_top2），
  核对最小成本、前两解的顺序与内容；
- 首解必须与旧接口 repair() / repair_redundant() 完全一致；
- 同串不同删位算两个互异方案；锁定位置在任何方案中都不可改、不可删；
- 未启用核查时两个 HTTP 接口的响应逐项不变；无解时不伪造备选。
"""

from __future__ import annotations

import itertools
import random
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repair import (
    OPEN_TO_CLOSE,
    repair,
    repair_candidates,
    repair_redundant,
    repair_redundant_candidates,
)
from tests.brute import brute_force_redundant_top2, brute_force_top2

CHARS = "()[]{}"
client = TestClient(app)


def run_plain(s, locked=None):
    n = len(s)
    locked = locked if locked is not None else [False] * n
    return repair_candidates(list(s), list(locked))


def run_redundant(s, locked=None):
    n = len(s)
    locked = locked if locked is not None else [False] * n
    return repair_redundant_candidates(list(s), list(locked))


def check_plain(chars, locked):
    expected = brute_force_top2(chars, locked)
    got = repair_candidates(chars, locked)
    if expected is None:
        assert got is None, f"{chars=} {locked=} 应无解，DP 给出 {got}"
        return
    assert got is not None, f"{chars=} {locked=} 应有解，DP 返回 None"
    # 前两解的内容与顺序完全一致
    assert [t for t, _ in got] == [t for t, _ in expected], (
        f"{''.join(chars)} {locked=} DP={[t for t, _ in got]} "
        f"暴力={[t for t, _ in expected]}"
    )
    # 互异且升序
    texts = [t for t, _ in got]
    assert len(texts) == len(set(texts))
    assert texts == sorted(texts)
    for (text, pairs), (exp_text, exp_cost) in zip(got, expected):
        # 最小成本一致
        assert sum(a != b for a, b in zip(chars, text)) == exp_cost
        # 锁定位置未被改动
        for i, lk in enumerate(locked):
            if lk:
                assert text[i] == chars[i], "锁定位置被改动"
        # 配对与栈式扫描一致、恰好覆盖全部位置
        stack = []
        derived = []
        for idx, ch in enumerate(text):
            if ch in OPEN_TO_CLOSE:
                stack.append(idx)
            else:
                o = stack.pop()
                assert OPEN_TO_CLOSE[text[o]] == ch
                derived.append([o, idx])
        assert not stack
        assert pairs == sorted(derived)
        assert sorted(p for pair in pairs for p in pair) == list(range(len(chars)))
    # 首解与旧接口完全一致
    assert got[0] == repair(chars, locked)


def check_redundant(chars, locked):
    expected = brute_force_redundant_top2(chars, locked)
    got = repair_redundant_candidates(chars, locked)
    if expected is None:
        assert got is None, f"{chars=} {locked=} 应无解，DP 给出 {got}"
        return
    assert got is not None, f"{chars=} {locked=} 应有解，DP 返回 None"
    n = len(chars)
    # 前两解的内容与顺序完全一致（含删位）
    assert [(t, d) for t, _, d in got] == [(t, d) for t, _, d in expected], (
        f"{''.join(chars)} {locked=} DP={[(t, d) for t, _, d in got]} "
        f"暴力={[(t, d) for t, _, d in expected]}"
    )
    # 互异且按 (修复串, 删位) 升序；None（未删除）只可能在唯一解中出现
    keys = [(t, d) for t, _, d in got]
    assert len(keys) == len(set(keys))
    assert keys == sorted(keys, key=lambda x: (x[0], x[1] if x[1] is not None else -1))
    for (text, pairs, deleted), (exp_text, exp_cost, exp_del) in zip(got, expected):
        assert deleted == exp_del
        kept = [i for i in range(n) if i != deleted]
        assert len(text) == len(kept)
        # 最小成本一致：删除计 1 次，替换逐位核对
        repl = sum(chars[i] != text[p] for p, i in enumerate(kept))
        assert repl + (deleted is not None) == exp_cost
        # 锁定保护：不可删、不可改
        if deleted is not None:
            assert not locked[deleted], "锁定位置被删除"
        for p, i in enumerate(kept):
            if locked[i]:
                assert text[p] == chars[i], "锁定位置被改动"
        # 配对回指原稿坐标、与栈式扫描一致、恰好覆盖全部未删位置
        stack = []
        derived = []
        for idx, ch in enumerate(text):
            if ch in OPEN_TO_CLOSE:
                stack.append(idx)
            else:
                o = stack.pop()
                assert OPEN_TO_CLOSE[text[o]] == ch
                derived.append([kept[o], kept[idx]])
        assert not stack
        assert pairs == sorted(derived)
        assert sorted(p for pair in pairs for p in pair) == kept
    # 首解与旧接口完全一致
    assert got[0] == repair_redundant(chars, locked)


class TestPlainExhaustive:
    @pytest.mark.parametrize("n", [2, 4])
    def test_exhaustive(self, n):
        """n=2: 144 种输入全枚举；n=4: 20736 种全枚举。"""
        seen_two_distinct = False
        for chars in itertools.product(CHARS, repeat=n):
            for locked in itertools.product([False, True], repeat=n):
                chars, locked = list(chars), list(locked)
                check_plain(chars, locked)
                got = repair_candidates(chars, locked)
                if got is not None and len(got) == 2:
                    seen_two_distinct = True
        # 穷举确实覆盖了"存在备选"的情形
        assert seen_two_distinct

    @pytest.mark.parametrize("n,samples", [(6, 2000), (8, 1000)])
    def test_random_sample(self, n, samples):
        rng = random.Random(20261006 + n)
        for _ in range(samples):
            chars = [rng.choice(CHARS) for _ in range(n)]
            locked = [rng.random() < 0.4 for _ in range(n)]
            check_plain(chars, locked)

    def test_random_biased_locked(self):
        rng = random.Random(17)
        for _ in range(1000):
            n = rng.choice([2, 4, 6, 8])
            chars = [rng.choice(CHARS) for _ in range(n)]
            locked = [rng.random() < 0.75 for _ in range(n)]
            check_plain(chars, locked)


class TestRedundantExhaustive:
    @pytest.mark.parametrize("n", [3, 4])
    def test_exhaustive(self, n):
        """n=3: 1728 种输入全枚举；n=4: 20736 种全枚举。"""
        seen_same_text_diff_deleted = False
        seen_two_distinct_texts = False
        for chars in itertools.product(CHARS, repeat=n):
            for locked in itertools.product([False, True], repeat=n):
                chars, locked = list(chars), list(locked)
                check_redundant(chars, locked)
                got = repair_redundant_candidates(chars, locked)
                if got is not None and len(got) == 2:
                    (t1, _, d1), (t2, _, d2) = got
                    if t1 == t2 and d1 != d2:
                        seen_same_text_diff_deleted = True
                    if t1 != t2:
                        seen_two_distinct_texts = True
        # 穷举确实覆盖了"同串不同删位"与"两个不同结果串"两类备选
        # （同串不同删位只可能出现在奇数长度——偶数长度不允许删除）
        if n % 2 == 1:
            assert seen_same_text_diff_deleted
        assert seen_two_distinct_texts

    @pytest.mark.parametrize("n,samples", [(5, 1500), (6, 1200), (7, 800), (8, 600)])
    def test_random_sample(self, n, samples):
        rng = random.Random(20261007 + n)
        for _ in range(samples):
            chars = [rng.choice(CHARS) for _ in range(n)]
            locked = [rng.random() < 0.4 for _ in range(n)]
            check_redundant(chars, locked)

    def test_random_biased_locked(self):
        rng = random.Random(23)
        for _ in range(800):
            n = rng.randint(3, 8)
            chars = [rng.choice(CHARS) for _ in range(n)]
            locked = [rng.random() < 0.75 for _ in range(n)]
            check_redundant(chars, locked)


class TestPlainSpecific:
    def test_two_tied_texts_order(self):
        # "(]"：改 "()" 与改 "[]" 同为 1 次修改，按字典序返回两个互异方案
        assert run_plain("(]") == [("()", [[0, 1]]), ("[]", [[0, 1]])]

    def test_unique_when_already_valid(self):
        # 零修改方案唯一
        assert run_plain("()") == [("()", [[0, 1]])]
        assert run_plain("({[]})", [True] * 6) == [("({[]})", [[0, 5], [1, 4], [2, 3]])]

    def test_cross_all_unlocked_two_solutions(self):
        # "([)]"：(()) 与 ()[] 同为改 2 处（([]) 与 [][] 也同成本但字典序更靠后）
        assert run_plain("([)]") == [
            ("(())", [[0, 3], [1, 2]]),
            ("()[]", [[0, 1], [2, 3]]),
        ]

    def test_locked_conflict_eliminates_alternative(self):
        # 锁定冲突：锁死首位的 "(" 后 "[]" 不再可行，方案唯一
        assert run_plain("(]", [True, False]) == [("()", [[0, 1]])]
        # 锁死次位的 "]" 后 "()" 不再可行
        assert run_plain("(]", [False, True]) == [("[]", [[0, 1]])]

    def test_locked_conflict_no_repair(self):
        # 全锁定且不合法：无解，不伪造备选
        assert run_plain("((", [True, True]) is None
        assert run_plain("([)]", [True] * 4) is None

    def test_empty(self):
        assert run_plain("") == [("", [])]


class TestRedundantSpecific:
    def test_same_text_different_deleted_positions(self):
        # "(()"：删 0 或删 1 都得 "()" 且同改 1 次——同串不同删位，
        # 必须列为两个互异方案，按删位升序
        assert run_redundant("(()") == [
            ("()", [[1, 2]], 0),
            ("()", [[0, 2]], 1),
        ]

    def test_same_text_different_deleted_positions_close(self):
        # "())"：删 1 或删 2 都得 "()"
        assert run_redundant("())") == [
            ("()", [[0, 2]], 1),
            ("()", [[0, 1]], 2),
        ]

    def test_same_text_three_deletions_top2(self):
        # "((]"：删 0/1/2 都能以 2 次修改得到 "()"，前二取删位 0、1
        assert run_redundant("((]") == [
            ("()", [[1, 2]], 0),
            ("()", [[0, 2]], 1),
        ]

    def test_two_distinct_texts(self):
        # "{)("：删 2 改 1 次得 "()"；删 1 改 1 次得 "{}"，同为 2 次修改，
        # 两个不同结果串按字典序排列
        assert run_redundant("{)(") == [
            ("()", [[0, 1]], 2),
            ("{}", [[0, 2]], 1),
        ]

    def test_locked_forces_unique(self):
        # 首位锁定后删位 0 不可用，"(()" 只剩删 1 一个最优方案
        assert run_redundant("(()", [True, False, False]) == [("()", [[0, 2]], 1)]
        # 下标 1 锁定后 "())" 只剩删 2
        assert run_redundant("())", [False, True, False]) == [("()", [[0, 1]], 2)]

    def test_locked_surplus_no_repair(self):
        # 无可行方案时不伪造备选
        assert run_redundant("(((", [True] * 3) is None
        assert run_redundant("()(", [False, False, True]) is None

    def test_even_length_unique_matches_repair(self):
        # 偶数长度不删除；合法串零修改唯一解
        assert run_redundant("()()", [True] * 4) == [("()()", [[0, 1], [2, 3]], None)]

    def test_empty(self):
        assert run_redundant("") == [("", [], None)]


class TestPerformance:
    @staticmethod
    def _mutated(rng, base):
        """从合法串出发只改未锁定位置，保证有解且走重负载路径。"""
        locked = [rng.random() < 0.3 for _ in base]
        chars = [
            c if lk or rng.random() < 0.5 else rng.choice(CHARS)
            for c, lk in zip(base, locked)
        ]
        return chars, locked

    def test_plain_max_length(self):
        rng = random.Random(160)
        chars, locked = self._mutated(rng, list("()" * 80))
        t0 = time.perf_counter()
        out = repair_candidates(chars, locked)
        assert time.perf_counter() - t0 < 5.0
        assert out is not None
        assert len(out[0][0]) == 160
        assert out[0] == repair(chars, locked)

    def test_redundant_max_length(self):
        rng = random.Random(81)
        chars, locked = self._mutated(rng, list("()" * 40 + "("))
        t0 = time.perf_counter()
        out = repair_redundant_candidates(chars, locked)
        assert time.perf_counter() - t0 < 5.0
        assert out is not None
        assert len(out[0][0]) == 80
        assert out[0] == repair_redundant(chars, locked)


def post(body):
    return client.post("/repair", json=body)


def post_redundant(body):
    return client.post("/repair-redundant", json=body)


def tokens(s, locked=None):
    n = len(s)
    locked = locked if locked is not None else [False] * n
    return [{"char": c, "locked": lk} for c, lk in zip(s, locked)]


class TestApiDisabledUnchanged:
    """未启用核查（缺省或显式 false）时，两个接口的响应逐项不变。"""

    def test_repair_ok_unchanged(self):
        r = post({"tokens": tokens("(]")})
        assert r.status_code == 200
        assert r.json() == {
            "status": "OK",
            "repaired": "()",
            "pairs": [[0, 1]],
            "changes": [{"index": 1, "before": "]", "after": ")"}],
        }

    def test_repair_explicit_false_unchanged(self):
        r = post({"tokens": tokens("(]"), "checkAmbiguity": False})
        assert r.status_code == 200
        assert "ambiguity" not in r.json()
        assert r.json()["repaired"] == "()"

    def test_repair_no_repair_unchanged(self):
        r = post({"tokens": tokens("((", [True, True])})
        assert r.json() == {
            "status": "NO_REPAIR",
            "repaired": None,
            "pairs": None,
            "changes": None,
        }

    def test_redundant_ok_unchanged(self):
        r = post_redundant({"tokens": tokens("(()")})
        assert r.status_code == 200
        assert r.json() == {
            "status": "OK",
            "repaired": "()",
            "pairs": [[1, 2]],
            "changes": [],
            "deletedIndex": 0,
        }

    def test_redundant_no_repair_unchanged(self):
        r = post_redundant({"tokens": tokens("(((", [True] * 3)})
        assert r.json() == {
            "status": "NO_REPAIR",
            "repaired": None,
            "pairs": None,
            "changes": None,
            "deletedIndex": None,
        }


class TestApiEnabled:
    def test_unique_solution(self):
        r = post({"tokens": tokens("()"), "checkAmbiguity": True})
        data = r.json()
        assert data["status"] == "OK"
        assert data["ambiguity"] == {
            "unique": True,
            "solutions": [
                {"repaired": "()", "pairs": [[0, 1]], "changes": []}
            ],
        }

    def test_two_solutions_ordered(self):
        r = post({"tokens": tokens("(]"), "checkAmbiguity": True})
        data = r.json()
        assert data["ambiguity"]["unique"] is False
        sols = data["ambiguity"]["solutions"]
        assert [s["repaired"] for s in sols] == ["()", "[]"]
        assert sols[0]["changes"] == [{"index": 1, "before": "]", "after": ")"}]
        assert sols[1]["changes"] == [{"index": 0, "before": "(", "after": "["}]
        # 首解与顶层字段一致
        assert sols[0]["repaired"] == data["repaired"]
        assert sols[0]["pairs"] == data["pairs"]
        assert sols[0]["changes"] == data["changes"]

    def test_locked_conflict_eliminates_alternative(self):
        r = post({"tokens": tokens("(]", [True, False]), "checkAmbiguity": True})
        data = r.json()
        assert data["ambiguity"]["unique"] is True
        assert data["ambiguity"]["solutions"][0]["repaired"] == "()"

    def test_no_repair_has_no_ambiguity(self):
        # 无解时不伪造备选：响应与旧的 NO_REPAIR 完全一致
        r = post({"tokens": tokens("((", [True, True]), "checkAmbiguity": True})
        assert r.json() == {
            "status": "NO_REPAIR",
            "repaired": None,
            "pairs": None,
            "changes": None,
        }

    def test_redundant_same_text_different_deleted(self):
        r = post_redundant({"tokens": tokens("(()"), "checkAmbiguity": True})
        data = r.json()
        assert data["ambiguity"]["unique"] is False
        sols = data["ambiguity"]["solutions"]
        # 同一结果串、不同删位：两个互异方案，按删位升序
        assert [s["repaired"] for s in sols] == ["()", "()"]
        assert [s["deletedIndex"] for s in sols] == [0, 1]
        assert sols[0]["pairs"] == [[1, 2]]
        assert sols[1]["pairs"] == [[0, 2]]
        # 首解与顶层字段一致
        assert sols[0]["repaired"] == data["repaired"]
        assert sols[0]["pairs"] == data["pairs"]
        assert sols[0]["deletedIndex"] == data["deletedIndex"]

    def test_redundant_locked_forces_unique(self):
        r = post_redundant(
            {"tokens": tokens("(()", [True, False, False]), "checkAmbiguity": True}
        )
        data = r.json()
        assert data["ambiguity"]["unique"] is True
        assert data["ambiguity"]["solutions"][0]["deletedIndex"] == 1

    def test_redundant_changes_point_to_original(self):
        # "})()("：唯一最优为删下标 4 并把下标 0 的 "}" 改为 "("
        r = post_redundant({"tokens": tokens("})()("), "checkAmbiguity": True})
        data = r.json()
        assert data["ambiguity"]["unique"] is True
        sol = data["ambiguity"]["solutions"][0]
        assert sol["repaired"] == "()()"
        assert sol["deletedIndex"] == 4
        assert sol["pairs"] == [[0, 1], [2, 3]]
        assert sol["changes"] == [{"index": 0, "before": "}", "after": "("}]

    def test_redundant_no_repair_has_no_ambiguity(self):
        r = post_redundant(
            {"tokens": tokens("(((", [True] * 3), "checkAmbiguity": True}
        )
        assert r.json() == {
            "status": "NO_REPAIR",
            "repaired": None,
            "pairs": None,
            "changes": None,
            "deletedIndex": None,
        }


class TestApiValidation:
    @pytest.mark.parametrize("bad", ["yes", 1, 0, "true"])
    def test_check_ambiguity_wrong_type_repair(self, bad):
        r = post({"tokens": tokens("()"), "checkAmbiguity": bad})
        assert r.status_code == 422

    @pytest.mark.parametrize("bad", ["yes", 1, 0, "true"])
    def test_check_ambiguity_wrong_type_redundant(self, bad):
        r = post_redundant({"tokens": tokens("(()"), "checkAmbiguity": bad})
        assert r.status_code == 422
