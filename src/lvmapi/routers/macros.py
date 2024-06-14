#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: macros.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter, HTTPException

import lvmapi.tools.macros


router = APIRouter(prefix="/macros", tags=["macros"])


@router.get("/shutdown")
async def shutdown() -> bool:
    """Performs an emergency shutdown of the enclosure and telescopes."""

    try:
        await lvmapi.tools.macros.shutdown()
    except Exception as ee:
        raise HTTPException(status_code=500, detail=str(ee))

    return True
