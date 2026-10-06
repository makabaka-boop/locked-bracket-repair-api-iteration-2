"""区间动态规划修复括号宏。

问题：给定 2..160 个偶数长度 token，每个位置有一个字符（()[]{} 之一）和
locked 标记。只允许修改未锁定位置的字符，使整串成为类型正确的平衡嵌套
序列。目标：先最小化修改数，再按 '(' ')' '[' ']' '{' '}' 的顺序取字典序
最小结果。无解返回 None。

做法：经典区间 DP。dp[i][j] 表示把区间 [i, j) 修复为合法括号序列的
(最小修改数, 字典序最小结果串)。长度为偶数的区间才有意义。

转移（len >= 2）：
  对 k = i+1, i+3, ..., j-1（步长 2）：
    若 [i+1, k) 与 [k+1, j) 均可修复，则枚举位置 i 的开括号 oc 与位置 k
    的匹配闭括号 cc（受 locked 约束），候选为：
        cost = (oc != s[i]) + (cc != s[k]) + cost(i+1,k) + cost(k+1,j)
        text = oc + text(i+1,k) + cc + text(k+1,j)
  取 (cost, text) 最小者。

注意：字典序比较基于 ASCII，而 '('=40 ')'=41 '['=91 ']'=93 '{'=123 '}'=125
恰好与要求的顺序一致，因此直接比较字符串即可。

复杂度：状态 O(n^2)，每状态转移 O(n)，总 O(n^3)。n=160 时约 8.7 万个
候选串拼接，毫秒级完成。

单个赘余标记变体（repair_redundant）：装配宏偶尔多抄一个未确认标记，
额外允许删除至多一个未锁定位置，删除与替换各计一次修改。状态增加
一维 d ∈ {0, 1} 表示区间内是否已删除，被删位置的原稿下标随状态
携带，因此配对与改动清单都能回指原稿坐标，而不必事后猜测删了哪一位。
并列时先取修复串字典序最小，再取被删下标最小。

歧义核查变体（repair_candidates / repair_redundant_candidates）：
审核员在接受自动修复前需要知道最小修改方案是否唯一。两个函数在同一
区间 DP 框架上把每个状态的"最优一个候选"换成"最小代价下按 key 升序的
前两个互异候选"，从而给出全局前两个互异方案与"唯一／存在备选"结论。
key 对普通修复是修复串本身，对赘余变体是 (修复串, 被删下标)——结果串
相同但删除的原稿位置不同算两个互异方案。这不是先求出旧首解再局部改
一个字符的事后修补，而是 DP 的每个状态都保留足够的候选信息；子区间
全体候选的组合中，前两名互异者必然落在两侧各自前二的组合里（任一
用到第三名之外候选的组合，都有至少两个互异组合严格不劣于它），因此
每状态保留两个候选不会丢失全局前二。不同解析路径产生的同一结果经
去重只计一次，不会被当成"备选"。
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
PAIRS = (("(", ")"), ("[", "]"), ("{", "}"))

# (cost, text)；cost 为 None 表示该区间不可修复
State = Tuple[Optional[int], Optional[str]]


def _pairs_of(text: str, deleted: int = -1) -> list:
    """由修复串重建配对下标（栈式扫描，与 DP 结构一致），按开括号下标升序。

    deleted >= 0 时把修复串坐标映射回原稿坐标：跳过被删位置（单调映射，
    保序），因此配对一律回指原稿。
    """
    pairs = []
    stack: list[int] = []
    for idx, ch in enumerate(text):
        if ch in OPEN_TO_CLOSE:
            stack.append(idx)
        else:
            o = stack.pop()
            if deleted >= 0:
                o = o + 1 if o >= deleted else o
                c = idx + 1 if idx >= deleted else idx
            else:
                c = idx
            pairs.append([o, c])
    pairs.sort()
    return pairs


def repair(chars: Sequence[str], locked: Sequence[bool]) -> Optional[Tuple[str, list]]:
    """修复括号序列。

    返回 (修复后的串, 配对下标列表)。配对列表按开括号下标升序给出
    [open_index, close_index]。不可修复时返回 None。
    """
    n = len(chars)
    if n == 0:
        return "", []
    if n % 2 != 0:
        return None

    INF: State = (None, None)
    # dp[i][j] 仅对偶数长度区间有效
    dp = [[INF] * (n + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][i] = (0, "")

    for length in range(2, n + 1, 2):
        for i in range(n + 1 - length):
            j = i + length
            best: State = INF
            for k in range(i + 1, j, 2):
                left = dp[i + 1][k]
                right = dp[k + 1][j]
                if left[0] is None or right[0] is None:
                    continue
                base = left[0] + right[0]
                inner = left[1]
                tail = right[1]
                for oc, cc in PAIRS:
                    if locked[i] and chars[i] != oc:
                        continue
                    if locked[k] and chars[k] != cc:
                        continue
                    cost = base + (chars[i] != oc) + (chars[k] != cc)
                    text = oc + inner + cc + tail
                    if best[0] is None or cost < best[0] or (
                        cost == best[0] and text < best[1]
                    ):
                        best = (cost, text)
            dp[i][j] = best

    if dp[0][n][0] is None:
        return None

    result = dp[0][n][1]
    return result, _pairs_of(result)


def repair_redundant(
    chars: Sequence[str], locked: Sequence[bool]
) -> Optional[Tuple[str, list, Optional[int]]]:
    """单个赘余标记修复：允许删除至多一个未锁定位置。

    删除与替换各计一次修改。奇数长度必须删除恰好一个位置；偶数长度
    删除一个位置后为奇数，不可能合法，因此结果与 repair() 完全一致。

    返回 (修复串, 配对下标, 被删下标或 None)；配对与删除下标一律为
    原稿零基坐标。并列时先取修复串字典序最小，再取被删下标最小。
    无解返回 None。
    """
    n = len(chars)
    if n == 0:
        return "", [], None

    # dp[d][i][j]：把区间 [i, j) 修复为合法串且区间内恰好删除 d 个位置
    # 的最优解 (cost, text, deleted)，不可达为 None。deleted 为被删位置
    # 的原稿下标（d=0 时为 -1）。是否已删除直接编码在状态里，原稿下标
    # 从不丢失。只有 d 与区间长度同奇偶的状态可达。
    dp = [[[None] * (n + 1) for _ in range(n + 1)] for _ in range(2)]
    for i in range(n + 1):
        dp[0][i][i] = (0, "", -1)

    for length in range(1, n + 1):
        d = length % 2
        for i in range(n + 1 - length):
            j = i + length
            best = None
            # 配对转移：位置 i 与 k 配成一对，删除（若 d=1）落在某一侧
            for k in range(i + 1, j):
                for dl in ((0, 1) if d else (0,)):
                    left = dp[dl][i + 1][k]
                    right = dp[d - dl][k + 1][j]
                    if left is None or right is None:
                        continue
                    base = left[0] + right[0]
                    inner, tail = left[1], right[1]
                    deleted = left[2] if dl else right[2]
                    for oc, cc in PAIRS:
                        if locked[i] and chars[i] != oc:
                            continue
                        if locked[k] and chars[k] != cc:
                            continue
                        cost = base + (chars[i] != oc) + (chars[k] != cc)
                        cand = (cost, oc + inner + cc + tail, deleted)
                        if best is None or cand < best:
                            best = cand
            if d:
                # 删除转移：直接删掉未锁定的 m（计 1 次），两侧各自平衡
                for m in range(i, j, 2):
                    if locked[m]:
                        continue
                    left = dp[0][i][m]
                    right = dp[0][m + 1][j]
                    if left is None or right is None:
                        continue
                    cand = (1 + left[0] + right[0], left[1] + right[1], m)
                    if best is None or cand < best:
                        best = cand
            dp[d][i][j] = best

    root = dp[n % 2][0][n]
    if root is None:
        return None
    _, text, deleted = root

    # 配对下标由修复串重建，再映射回原稿坐标
    return text, _pairs_of(text, deleted), (deleted if deleted >= 0 else None)


class _Top2:
    """单状态候选收集器：记录最小代价，及该代价下按 key 升序的前两个互异 key。

    不同解析路径产生的同一 key 只保留一次（去重），保证"前二"是两个
    真正互异的方案，而不是同一结果的两条推导。
    """

    __slots__ = ("cost", "keys")

    def __init__(self) -> None:
        self.cost: Optional[int] = None
        self.keys: list = []

    def add(self, cost: int, key) -> None:
        if self.cost is None or cost < self.cost:
            self.cost = cost
            self.keys = [key]
        elif cost == self.cost and key not in self.keys:
            self.keys.append(key)
            self.keys.sort()
            del self.keys[2:]


def repair_candidates(
    chars: Sequence[str], locked: Sequence[bool]
) -> Optional[List[Tuple[str, list]]]:
    """歧义核查：最小修改数下按字典序排列的前两个互异修复方案。

    与 repair() 同一区间 DP 框架，但每个状态保留最小代价下字典序前二的
    互异修复串，而非只保留最优者。全局前二必可由子状态前二组合得到
    （见模块 docstring），因此不会退化成"固定首解再局部改一个字符"。

    返回 [(修复串, 配对下标), ...]，按字典序升序；长度 1 表示方案唯一，
    长度 2 表示存在备选。无解返回 None。
    """
    n = len(chars)
    if n == 0:
        return [("", [])]
    if n % 2 != 0:
        return None

    # dp[i][j]：区间 [i, j) 的 _Top2（仅偶数长度区间可达），不可达为 None
    dp: list = [[None] * (n + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        t = _Top2()
        t.add(0, "")
        dp[i][i] = t

    for length in range(2, n + 1, 2):
        for i in range(n + 1 - length):
            j = i + length
            acc = _Top2()
            for k in range(i + 1, j, 2):
                left = dp[i + 1][k]
                right = dp[k + 1][j]
                if left is None or right is None:
                    continue
                base = left.cost + right.cost
                lkeys, rkeys = left.keys, right.keys
                for oc, cc in PAIRS:
                    if locked[i] and chars[i] != oc:
                        continue
                    if locked[k] and chars[k] != cc:
                        continue
                    cost = base + (chars[i] != oc) + (chars[k] != cc)
                    if acc.cost is not None and cost > acc.cost:
                        continue  # 该转移已不可能进入前二，跳过拼串
                    # (次优左, 次优右) 不优于 (最优左, 次优右) 与
                    # (次优左, 最优右) 中的任何一个，必不在前二，无需构造
                    acc.add(cost, oc + lkeys[0] + cc + rkeys[0])
                    if len(lkeys) > 1:
                        acc.add(cost, oc + lkeys[1] + cc + rkeys[0])
                    if len(rkeys) > 1:
                        acc.add(cost, oc + lkeys[0] + cc + rkeys[1])
            dp[i][j] = acc if acc.cost is not None else None

    root = dp[0][n]
    if root is None:
        return None
    return [(text, _pairs_of(text)) for text in root.keys]


def repair_redundant_candidates(
    chars: Sequence[str], locked: Sequence[bool]
) -> Optional[List[Tuple[str, list, Optional[int]]]]:
    """单赘余标记修复的歧义核查：前两个互异方案。

    互异按 (修复串, 被删下标) 判定：结果串相同但删除的原稿位置不同算
    两个方案，必须分别列出。排序键为 (修复串字典序, 被删下标)，与
    repair_redundant 的裁决顺序一致。状态 dp[d][i][j] 保留最小代价下
    按 key 升序的前两个互异 key，正确性论证同 repair_candidates。

    返回 [(修复串, 配对下标, 被删下标或 None), ...]，一律原稿坐标；
    长度 1 唯一、长度 2 存在备选。无解返回 None。
    """
    n = len(chars)
    if n == 0:
        return [("", [], None)]

    # dp[d][i][j]：区间 [i, j) 恰好删除 d 个位置的 _Top2，key 为
    # (修复串, 被删下标)，d=0 时被删下标恒为 -1；不可达为 None
    dp: list = [[[None] * (n + 1) for _ in range(n + 1)] for _ in range(2)]
    for i in range(n + 1):
        t = _Top2()
        t.add(0, ("", -1))
        dp[0][i][i] = t

    for length in range(1, n + 1):
        d = length % 2
        for i in range(n + 1 - length):
            j = i + length
            acc = _Top2()
            # 配对转移：位置 i 与 k 配成一对，删除（若 d=1）落在某一侧
            for k in range(i + 1, j):
                for dl in ((0, 1) if d else (0,)):
                    left = dp[dl][i + 1][k]
                    right = dp[d - dl][k + 1][j]
                    if left is None or right is None:
                        continue
                    base = left.cost + right.cost
                    lkeys, rkeys = left.keys, right.keys
                    for oc, cc in PAIRS:
                        if locked[i] and chars[i] != oc:
                            continue
                        if locked[k] and chars[k] != cc:
                            continue
                        cost = base + (chars[i] != oc) + (chars[k] != cc)
                        if acc.cost is not None and cost > acc.cost:
                            continue  # 该转移已不可能进入前二，跳过拼串
                        # 同 repair_candidates：(次优, 次优) 组合必不在前二
                        cand = [(lkeys[0], rkeys[0])]
                        if len(lkeys) > 1:
                            cand.append((lkeys[1], rkeys[0]))
                        if len(rkeys) > 1:
                            cand.append((lkeys[0], rkeys[1]))
                        for (lt, ld), (rt, rd) in cand:
                            acc.add(cost, (oc + lt + cc + rt, ld if dl else rd))
            if d:
                # 删除转移：直接删掉未锁定的 m（计 1 次），两侧各自平衡
                for m in range(i, j, 2):
                    if locked[m]:
                        continue
                    left = dp[0][i][m]
                    right = dp[0][m + 1][j]
                    if left is None or right is None:
                        continue
                    cost = 1 + left.cost + right.cost
                    if acc.cost is not None and cost > acc.cost:
                        continue
                    cand = [(left.keys[0], right.keys[0])]
                    if len(left.keys) > 1:
                        cand.append((left.keys[1], right.keys[0]))
                    if len(right.keys) > 1:
                        cand.append((left.keys[0], right.keys[1]))
                    for (lt, _), (rt, _) in cand:
                        acc.add(cost, (lt + rt, m))
            dp[d][i][j] = acc if acc.cost is not None else None

    root = dp[n % 2][0][n]
    if root is None:
        return None
    return [
        (text, _pairs_of(text, deleted), (deleted if deleted >= 0 else None))
        for text, deleted in root.keys
    ]
