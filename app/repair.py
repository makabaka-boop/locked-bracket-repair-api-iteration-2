"""区间动态规划修复括号宏。

问题：给定 2..160 个偶数长度 token，每个位置有一个字符（()[]{} 之一）和
locked 标记。只允许修改未锁定位置的字符，使整串成为类型正确的平衡嵌套
序列。目标：先最小化修改数，再按 '(' ')' '[' ']' '{' '}' 的顺序取字典序
最小结果。无解返回 None。

做法：经典区间 DP。dp[i][j] 表示把区间 [i, j) 修复为合法括号序列的若干
最优候选。普通修复的候选键为 (修改数, 结果串)；赘余修复还携带被删原稿
下标，候选键为 (修改数, 结果串, 被删下标)。

需要歧义核查时，每个区间保留按候选键排序的前两个互异候选，而不是只保留
旧首解；核查关闭时只保留一个候选，因此旧路径的性能不变。子区间的前两名
足以生成父区间的前两名：固定另一侧的最优子解后，排在第三名以后的子解前
面至少已有两个更优、且在父级仍互异的方案。不同解析路径可能生成同一结果
串与同一删位，状态合并时按完整方案键去重。

转移（len >= 2）：
  对 k = i+1, i+3, ..., j-1（步长 2）：
    枚举左右子区间候选，再枚举位置 i 的开括号 oc 与位置 k 的匹配闭括号
    cc（受 locked 约束），候选为：
        cost = (oc != s[i]) + (cc != s[k]) + cost(i+1,k) + cost(k+1,j)
        text = oc + text(i+1,k) + cc + text(k+1,j)

注意：字典序比较基于 ASCII，而 '('=40 ')'=41 '['=91 ']'=93 '{'=123 '}'=125
恰好与要求的顺序一致，因此直接比较字符串即可。

单个赘余标记变体（repair_redundant）：装配宏偶尔多抄一个未确认标记，
额外允许删除至多一个未锁定位置，删除与替换各计一次修改。状态增加
一维 d ∈ {0, 1} 表示区间内是否已删除，被删位置的原稿下标随状态
携带，因此配对与改动清单都能回指原稿坐标，而不必事后猜测删了哪一位。
并列时先取修复串字典序最小，再取被删下标最小。
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
PAIRS = (("(", ")"), ("[", "]"), ("{", "}"))

Candidate = Tuple[int, ...]


def _keep_top_candidates(
    best: list[Candidate], candidate: Candidate, limit: int
) -> None:
    """保留按完整候选元组排序的前 ``limit`` 个互异方案。

    第一维固定是修改数；其余维度构成方案身份。普通修复为 ``(text,)``，
    赘余修复为 ``(text, deleted_index)``。因此结果串相同但删位不同的两个
    方案不会互相覆盖，而不同解析路径得到的同一方案只计一次。
    """
    identity = candidate[1:]
    if any(existing[1:] == identity for existing in best):
        return
    best.append(candidate)
    best.sort()
    if len(best) > limit:
        del best[limit:]


def _repair_candidates(
    chars: Sequence[str], locked: Sequence[bool], check_ambiguity: bool
) -> list[Tuple[int, str]]:
    """返回整串普通修复所需的区间 DP 根候选（已排序去重）。"""
    limit = 2 if check_ambiguity else 1
    n = len(chars)
    if n == 0:
        return [(0, "")]
    if n % 2 != 0:
        return []

    # dp[i][j] 仅对偶数长度区间有效，保存至多两个互异候选。
    dp: list[list[list[Tuple[int, str]]]] = [
        [[] for _ in range(n + 1)] for _ in range(n + 1)
    ]
    for i in range(n + 1):
        dp[i][i] = [(0, "")]

    for length in range(2, n + 1, 2):
        for i in range(n + 1 - length):
            j = i + length
            best: list[Tuple[int, str]] = []
            for k in range(i + 1, j, 2):
                left_candidates = dp[i + 1][k]
                right_candidates = dp[k + 1][j]
                if not left_candidates or not right_candidates:
                    continue
                for left_cost, inner in left_candidates:
                    for right_cost, tail in right_candidates:
                        base = left_cost + right_cost
                        for oc, cc in PAIRS:
                            if locked[i] and chars[i] != oc:
                                continue
                            if locked[k] and chars[k] != cc:
                                continue
                            cost = (
                                base
                                + (chars[i] != oc)
                                + (chars[k] != cc)
                            )
                            _keep_top_candidates(
                                best,
                                (cost, oc + inner + cc + tail),
                                limit,
                            )
            dp[i][j] = best

    return dp[0][n]


def _build_pairs(text: str, deleted: int = -1) -> list[list[int]]:
    """从修复串重建配对，并把坐标映射回原稿。"""
    def to_orig(position: int) -> int:
        return position + 1 if deleted >= 0 and position >= deleted else position

    pairs = []
    stack: list[int] = []
    for idx, ch in enumerate(text):
        if ch in OPEN_TO_CLOSE:
            stack.append(idx)
        else:
            pairs.append([to_orig(stack.pop()), to_orig(idx)])
    pairs.sort()
    return pairs


def repair(
    chars: Sequence[str],
    locked: Sequence[bool],
    check_ambiguity: bool = False,
) -> Optional[Any]:
    """修复括号序列。

    默认返回 ``(修复后的串, 配对下标列表)``。配对列表按开括号下标升序给出
    [open_index, close_index]。不可修复时返回 None。

    ``check_ambiguity=True`` 时返回
    ``(首解串, 首解配对, 最少修改数下的前两个互异方案列表)``。列表中的方案
    为 ``cost/repaired/pairs`` 字典，按结果串字典序排列。
    """
    candidates = _repair_candidates(chars, locked, check_ambiguity)
    if not candidates:
        return None

    minimum_cost = candidates[0][0]
    plans = [
        {
            "cost": cost,
            "repaired": text,
            "pairs": _build_pairs(text),
        }
        for cost, text in candidates
        if cost == minimum_cost
    ]

    first = plans[0]
    if not check_ambiguity:
        return first["repaired"], first["pairs"]
    return first["repaired"], first["pairs"], plans


def _redundant_candidates(
    chars: Sequence[str], locked: Sequence[bool], check_ambiguity: bool
) -> list[Tuple[int, str, int]]:
    """返回至多一个删位时的区间 DP 根候选（已排序去重）。"""
    limit = 2 if check_ambiguity else 1
    n = len(chars)
    if n == 0:
        return [(0, "", -1)]

    # dp[d][i][j]：把区间 [i, j) 修复为合法串且区间内恰好删除 d 个位置
    # 的前两个互异候选 (cost, text, deleted)。deleted 为被删位置的原稿
    # 下标（d=0 时为 -1）。只有 d 与区间长度同奇偶的状态可达。
    dp: list[list[list[list[Tuple[int, str, int]]]]] = [
        [[[] for _ in range(n + 1)] for _ in range(n + 1)] for _ in range(2)
    ]
    for i in range(n + 1):
        dp[0][i][i] = [(0, "", -1)]

    for length in range(1, n + 1):
        d = length % 2
        for i in range(n + 1 - length):
            j = i + length
            best: list[Tuple[int, str, int]] = []

            # 配对转移：位置 i 与 k 配成一对，删除（若 d=1）落在某一侧。
            for k in range(i + 1, j):
                for dl in ((0, 1) if d else (0,)):
                    left_candidates = dp[dl][i + 1][k]
                    right_candidates = dp[d - dl][k + 1][j]
                    if not left_candidates or not right_candidates:
                        continue
                    for left in left_candidates:
                        for right in right_candidates:
                            left_cost, inner, left_deleted = left
                            right_cost, tail, right_deleted = right
                            deleted = left_deleted if dl else right_deleted
                            base = left_cost + right_cost
                            for oc, cc in PAIRS:
                                if locked[i] and chars[i] != oc:
                                    continue
                                if locked[k] and chars[k] != cc:
                                    continue
                                cost = (
                                    base
                                    + (chars[i] != oc)
                                    + (chars[k] != cc)
                                )
                                _keep_top_candidates(
                                    best,
                                    (cost, oc + inner + cc + tail, deleted),
                                    limit,
                                )

            if d:
                # 删除转移：直接删掉未锁定的 m（计 1 次），两侧各自平衡。
                for m in range(i, j, 2):
                    if locked[m]:
                        continue
                    left_candidates = dp[0][i][m]
                    right_candidates = dp[0][m + 1][j]
                    if not left_candidates or not right_candidates:
                        continue
                    for left_cost, inner, _ in left_candidates:
                        for right_cost, tail, _ in right_candidates:
                            _keep_top_candidates(
                                best,
                                (1 + left_cost + right_cost, inner + tail, m),
                                limit,
                            )
            dp[d][i][j] = best

    return dp[n % 2][0][n]


def repair_redundant(
    chars: Sequence[str],
    locked: Sequence[bool],
    check_ambiguity: bool = False,
) -> Optional[Any]:
    """单个赘余标记修复：允许删除至多一个未锁定位置。

    删除与替换各计一次修改。奇数长度必须删除恰好一个位置；偶数长度
    删除一个位置后为奇数，不可能合法，因此结果与 repair() 完全一致。

    默认返回 ``(修复串, 配对下标, 被删下标或 None)``；配对与删除下标一律
    为原稿零基坐标。并列时先取修复串字典序最小，再取被删下标最小。无解
    返回 None。

    ``check_ambiguity=True`` 时额外返回第四个元素：最少修改数下的前两个
    互异方案列表，每项为 ``cost/repaired/pairs/deleted_index`` 字典。方案
    身份同时包含结果串与删位，因此同串不同删位会作为不同方案保留。
    """
    candidates = _redundant_candidates(chars, locked, check_ambiguity)
    if not candidates:
        return None

    minimum_cost = candidates[0][0]
    plans = []
    for cost, text, deleted in candidates:
        if cost != minimum_cost:
            continue
        deleted_index = deleted if deleted >= 0 else None
        plans.append(
            {
                "cost": cost,
                "repaired": text,
                "pairs": _build_pairs(text, deleted),
                "deleted_index": deleted_index,
            }
        )

    first = plans[0]
    text = first["repaired"]
    pairs = first["pairs"]
    deleted_index = first["deleted_index"]
    if not check_ambiguity:
        return text, pairs, deleted_index
    return text, pairs, deleted_index, plans
