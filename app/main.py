"""FastAPI 入口：POST /repair 修复括号宏；POST /repair-redundant 单个赘余标记修复。

两个端点都支持可选的歧义核查（请求字段 checkAmbiguity）：为 true 时
响应额外携带 ambiguity 块，给出最小修改数下按既有顺序（修复串字典序，
赘余变体再按被删下标）排列的前两个互异方案与"唯一／存在备选"结论；
每个方案的配对、改动与删除位置均回指原稿坐标。未启用时响应与不支持
该选项的旧版本逐项一致（response_model_exclude_unset 保证 ambiguity
字段完全不出现）；无解时不伪造备选，响应与旧的 NO_REPAIR 完全一致。
"""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import FastAPI

from .repair import repair, repair_candidates, repair_redundant, repair_redundant_candidates
from .schemas import (
    ChangeItem,
    RedundantAmbiguity,
    RedundantRepairRequest,
    RedundantRepairResponse,
    RedundantSolution,
    RepairAmbiguity,
    RepairRequest,
    RepairResponse,
    RepairSolution,
)

app = FastAPI(title="Macro Repair API", version="1.2.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _change_items(
    chars: Sequence[str], result: str, deleted: Optional[int] = None
) -> list:
    """改动清单（原稿坐标）；deleted 不为 None 时跳过被删位置。"""
    changes = []
    for i, before in enumerate(chars):
        if i == deleted:
            continue
        p = i if deleted is None or i < deleted else i - 1
        after = result[p]
        if before != after:
            changes.append(ChangeItem(index=i, before=before, after=after))
    return changes


@app.post("/repair", response_model=RepairResponse, response_model_exclude_unset=True)
def repair_endpoint(req: RepairRequest) -> RepairResponse:
    chars = [t.char for t in req.tokens]
    locked = [t.locked for t in req.tokens]

    if req.checkAmbiguity:
        sols = repair_candidates(chars, locked)
        if sols is None:
            return RepairResponse(
                status="NO_REPAIR", repaired=None, pairs=None, changes=None
            )
        result, pairs = sols[0]
        return RepairResponse(
            status="OK",
            repaired=result,
            pairs=pairs,
            changes=_change_items(chars, result),
            ambiguity=RepairAmbiguity(
                unique=len(sols) == 1,
                solutions=[
                    RepairSolution(
                        repaired=text,
                        pairs=sol_pairs,
                        changes=_change_items(chars, text),
                    )
                    for text, sol_pairs in sols
                ],
            ),
        )

    outcome = repair(chars, locked)
    if outcome is None:
        return RepairResponse(
            status="NO_REPAIR", repaired=None, pairs=None, changes=None
        )

    result, pairs = outcome
    return RepairResponse(
        status="OK",
        repaired=result,
        pairs=pairs,
        changes=_change_items(chars, result),
    )


@app.post(
    "/repair-redundant",
    response_model=RedundantRepairResponse,
    response_model_exclude_unset=True,
)
def repair_redundant_endpoint(req: RedundantRepairRequest) -> RedundantRepairResponse:
    chars = [t.char for t in req.tokens]
    locked = [t.locked for t in req.tokens]

    if req.checkAmbiguity:
        sols = repair_redundant_candidates(chars, locked)
        if sols is None:
            return RedundantRepairResponse(
                status="NO_REPAIR",
                repaired=None,
                pairs=None,
                changes=None,
                deletedIndex=None,
            )
        result, pairs, deleted = sols[0]
        return RedundantRepairResponse(
            status="OK",
            repaired=result,
            pairs=pairs,
            changes=_change_items(chars, result, deleted),
            deletedIndex=deleted,
            ambiguity=RedundantAmbiguity(
                unique=len(sols) == 1,
                solutions=[
                    RedundantSolution(
                        repaired=text,
                        pairs=sol_pairs,
                        changes=_change_items(chars, text, sol_deleted),
                        deletedIndex=sol_deleted,
                    )
                    for text, sol_pairs, sol_deleted in sols
                ],
            ),
        )

    outcome = repair_redundant(chars, locked)
    if outcome is None:
        return RedundantRepairResponse(
            status="NO_REPAIR",
            repaired=None,
            pairs=None,
            changes=None,
            deletedIndex=None,
        )

    result, pairs, deleted = outcome
    return RedundantRepairResponse(
        status="OK",
        repaired=result,
        pairs=pairs,
        changes=_change_items(chars, result, deleted),
        deletedIndex=deleted,
    )
