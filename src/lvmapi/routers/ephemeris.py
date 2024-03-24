#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-24
# @Filename: ephemeris.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from lvmapi.tools.schedule import get_ephemeris_summary


class EphemerisSummaryOut(BaseModel):
    """Summary of the ephemeris."""

    SJD: int
    date: str
    sunset: float
    twilight_end: float
    twilight_start: float
    sunrise: float
    is_night: bool
    is_twilight: bool
    time_to_sunset: float
    time_to_sunrise: float
    from_file: bool


router = APIRouter(prefix="/ephemeris", tags=["ephemeris"])


@router.get("/")
@router.get(
    "/summary",
    description="Summary of the ephemeris",
    response_model=EphemerisSummaryOut,
)
async def get_summary():
    """Returns a summary of the ephemeris."""

    return get_ephemeris_summary()
