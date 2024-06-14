#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: enclosure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lvmapi.tools.gort import get_gort_client


class EnclosureStatus(BaseModel):
    """Status of the telescope enclosure."""

    open: bool
    moving: bool


router = APIRouter(prefix="/enclosure", tags=["enclosure"])


@router.get("/")
@router.get("/status")
async def status(request: Request) -> EnclosureStatus:
    """Performs an emergency shutdown of the enclosure and telescopes."""

    try:
        async with get_gort_client(request.app) as gort:
            status = await gort.enclosure.status()
    except Exception as ee:

        raise HTTPException(status_code=500, detail=str(ee))

    dome_status_labels = status["dome_status_labels"]

    return EnclosureStatus(
        open=("OPEN" in dome_status_labels),
        moving=("MOVING" in dome_status_labels),
    )
