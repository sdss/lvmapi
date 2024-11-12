#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from time import time

from typing import Annotated

from fastapi import APIRouter, Query


router = APIRouter(prefix="/transparency", tags=["transparency"])


@router.get("/", summary="Transparency measurements")
async def route_get_transparency(
    start_time: Annotated[
        float | None,
        Query(description="Start time as a UNIX timestamp"),
    ] = None,
    end_time: Annotated[
        float | None,
        Query(description="End time as a UNIX timestamp"),
    ] = None,
):
    """Returns transparency measurements.

    Without any parameters, returns the transparency measurements for the last hour.

    """

    if start_time is None or end_time is None:
        end_time = time()
        start_time = end_time - 3600
