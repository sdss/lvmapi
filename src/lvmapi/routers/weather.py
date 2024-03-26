#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-26
# @Filename: weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import polars
from fastapi import APIRouter

from lvmapi.tools.weather import get_weather_data


router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/")
@router.get("/report")
async def get_weather(station: str = "DuPont") -> list[dict]:
    """Returns the weather report (last 60 minutes) from a weather station."""

    df = await get_weather_data(station=station)

    return df.with_columns(ts=polars.col.ts.dt.to_string("%FT%X")).to_dicts()
