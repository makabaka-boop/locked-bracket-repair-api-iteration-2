"""FastAPI 入口：POST /repair 修复括号宏；POST /repair-redundant 单个赘余标记修复。"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from .repair import repair, repair_redundant
from .schemas import (
    AmbiguityInfo,
    AmbiguousRedundantRepairResponse,
    AmbiguousRepairResponse,
    ChangeItem,
    NoRepairResponse,
    RedundantAmbiguityInfo,
    RedundantNoRepairResponse,
    RedundantRepairAlternative,
    RedundantRepairRequest,
    RedundantRepairResultResponse,
    RedundantRepairResponse,
    RepairAlternative,
    RepairRequest,
    RepairResultResponse,
    RepairResponse,
)

app = FastAPI(title="Macro Repair API", version="1.2.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _changes_for(chars, repaired: str, deleted_index: Optional[int] = None):
    """构造回指原稿坐标的替换清单。"""
    changes = []
    for i, before in enumerate(chars):
        if i == deleted_index:
            continue
        position = (
            i if deleted_index is None or i < deleted_index else i - 1
        )
        after = repaired[position]
        if before != after:
            changes.append(ChangeItem(index=i, before=before, after=after))
    return changes


@app.post(
    "/repair",
    response_model=None,
    responses={200: {"model": RepairResultResponse}},
)
def repair_endpoint(req: RepairRequest):
    chars = [t.char for t in req.tokens]
    locked = [t.locked for t in req.tokens]

    outcome = repair(chars, locked, check_ambiguity=req.checkAmbiguity)
    if outcome is None:
        return NoRepairResponse(status="NO_REPAIR")

    if not req.checkAmbiguity:
        result, pairs = outcome
        return RepairResponse(
            status="OK",
            repaired=result,
            pairs=pairs,
            changes=_changes_for(chars, result),
        )

    result, pairs, plans = outcome
    alternatives = [
        RepairAlternative(
            repaired=plan["repaired"],
            pairs=plan["pairs"],
            changes=_changes_for(chars, plan["repaired"]),
        )
        for plan in plans[1:]
    ]
    status = "UNIQUE" if not alternatives else "ALTERNATIVE_EXISTS"
    return AmbiguousRepairResponse(
        status="OK",
        repaired=result,
        pairs=pairs,
        changes=_changes_for(chars, result),
        ambiguity=AmbiguityInfo(status=status, alternatives=alternatives),
    )


@app.post(
    "/repair-redundant",
    response_model=None,
    responses={200: {"model": RedundantRepairResultResponse}},
)
def repair_redundant_endpoint(req: RedundantRepairRequest):
    chars = [t.char for t in req.tokens]
    locked = [t.locked for t in req.tokens]

    outcome = repair_redundant(
        chars, locked, check_ambiguity=req.checkAmbiguity
    )
    if outcome is None:
        return RedundantNoRepairResponse(status="NO_REPAIR")

    if not req.checkAmbiguity:
        result, pairs, deleted_index = outcome
        return RedundantRepairResponse(
            status="OK",
            repaired=result,
            pairs=pairs,
            changes=_changes_for(chars, result, deleted_index),
            deletedIndex=deleted_index,
        )

    result, pairs, deleted_index, plans = outcome
    alternatives = [
        RedundantRepairAlternative(
            repaired=plan["repaired"],
            pairs=plan["pairs"],
            changes=_changes_for(
                chars, plan["repaired"], plan["deleted_index"]
            ),
            deletedIndex=plan["deleted_index"],
        )
        for plan in plans[1:]
    ]
    status = "UNIQUE" if not alternatives else "ALTERNATIVE_EXISTS"
    return AmbiguousRedundantRepairResponse(
        status="OK",
        repaired=result,
        pairs=pairs,
        changes=_changes_for(chars, result, deleted_index),
        deletedIndex=deleted_index,
        ambiguity=RedundantAmbiguityInfo(
            status=status, alternatives=alternatives
        ),
    )
