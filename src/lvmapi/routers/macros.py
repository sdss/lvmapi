#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from lvmapi.tools.gort import get_gort_client


router = APIRouter(prefix="/macros", tags=["macros"])


@router.get("/shutdown")
async def shutdown(request: Request, block: bool = True) -> bool:
    """Performs an emergency shutdown of the enclosure and telescopes."""

    try:
        async with get_gort_client(request.app) as gort:
            task = asyncio.create_task(gort.shutdown(park_telescopes=True))
            if block:
                await task
    except Exception as ee:
        raise HTTPException(status_code=500, detail=str(ee))

    return True
