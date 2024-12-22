#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-24
# @Filename: ephemeris.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from lvmopstools.ephemeris import get_ephemeris_summary
from sdsstools import get_sjd


class EphemerisSummaryOut(BaseModel):
    """Summary of the ephemeris."""

    SJD: int
    request_jd: float
    date: str
    sunset: float
    twilight_end: float
    twilight_start: float
    sunrise: float
    is_night: bool
    is_twilight: bool
    time_to_sunset: float
    time_to_sunrise: float
    moon_illumination: float
    from_file: bool


router = APIRouter(prefix="/ephemeris", tags=["ephemeris"])


@router.get(
    "/summary",
    summary="Summary of the ephemeris",
    response_model=EphemerisSummaryOut,
)
async def route_get_summary(
    sjd: Annotated[
        int | None,
        Query(description="The SJD for which to retrieve the ephemeris summary"),
    ] = None,
):
    """Returns a summary of the ephemeris for an SJD."""

    return get_ephemeris_summary(sjd=sjd)


@router.get("/sjd", summary="Get current SJD")
async def route_get_sjd() -> int:
    return get_sjd("LCO")
