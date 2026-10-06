"""请求/响应模型。

校验规则：
- /repair：tokens 为 2..160 个、长度必须为偶数；
- /repair-redundant：tokens 为 3..81 个，奇偶均可（奇数长度期望删去
  恰好一个赘余标记）；
- 每项仅含 char 与 locked 两个字段，额外字段一律 422；
- char 只能是 ()[]{} 之一（Literal 同时保证是字符串）；
- locked 必须是严格的 JSON 布尔值（StrictBool 拒绝 0/1、"true" 等）。

可选的歧义核查：两个请求模型都接受 checkAmbiguity（严格布尔，默认
false）。为 true 时响应额外携带 ambiguity 字段，给出最小修改数下的
前两个互异方案与"唯一／存在备选"结论；为 false（或未提供）时响应
与不支持该选项的旧版本逐项一致（ambiguity 字段完全不出现）。
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

BracketChar = Literal["(", ")", "[", "]", "{", "}"]


class TokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    char: BracketChar
    locked: StrictBool


class RepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokens: List[TokenIn] = Field(min_length=2, max_length=160)
    # 歧义核查开关：为 true 时响应附带 ambiguity 块
    checkAmbiguity: StrictBool = False

    @model_validator(mode="after")
    def _even_length(self) -> "RepairRequest":
        if len(self.tokens) % 2 != 0:
            raise ValueError("tokens length must be even")
        return self


class ChangeItem(BaseModel):
    index: int
    before: BracketChar
    after: BracketChar


class RepairSolution(BaseModel):
    """单个修复方案；pairs 与 changes 均回指原稿坐标。"""

    repaired: str
    pairs: List[List[int]]
    changes: List[ChangeItem]


class RepairAmbiguity(BaseModel):
    """歧义核查结论：unique 为 true 表示最小修改方案唯一。"""

    unique: bool
    solutions: List[RepairSolution]


class RepairResponse(BaseModel):
    status: Literal["OK", "NO_REPAIR"]
    repaired: Optional[str] = None
    pairs: Optional[List[List[int]]] = None
    changes: Optional[List[ChangeItem]] = None
    # 仅在 checkAmbiguity=true 且有解时由端点显式设置；未启用核查时
    # 该字段不出现在响应中（response_model_exclude_unset）
    ambiguity: Optional[RepairAmbiguity] = None


class RedundantRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tokens: List[TokenIn] = Field(min_length=3, max_length=81)
    # 歧义核查开关：为 true 时响应附带 ambiguity 块
    checkAmbiguity: StrictBool = False


class RedundantSolution(BaseModel):
    """单个赘余修复方案；pairs、changes、deletedIndex 均回指原稿坐标。"""

    repaired: str
    pairs: List[List[int]]
    changes: List[ChangeItem]
    deletedIndex: Optional[int] = None


class RedundantAmbiguity(BaseModel):
    """歧义核查结论；同串不同删位也算两个互异方案。"""

    unique: bool
    solutions: List[RedundantSolution]


class RedundantRepairResponse(BaseModel):
    status: Literal["OK", "NO_REPAIR"]
    repaired: Optional[str] = None
    pairs: Optional[List[List[int]]] = None
    changes: Optional[List[ChangeItem]] = None
    # 被删除位置的原稿零基下标；未删除（偶数长度）或 NO_REPAIR 时为 null
    deletedIndex: Optional[int] = None
    # 仅在 checkAmbiguity=true 且有解时出现
    ambiguity: Optional[RedundantAmbiguity] = None
