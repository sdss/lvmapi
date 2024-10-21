#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-03-26
# @Filename: weather.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Annotated

import polars
from fastapi import APIRouter, HTTPException, Query

from lvmapi.tools.weather import get_weather_data


router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/", summary="Weather report")
@router.get("/report", summary="Weather report")
async def route_get_weather(
    station: Annotated[
        str,
        Query(description="The weather station to query"),
    ] = "DuPont",
    start_time: Annotated[
        str | None,
        Query(description="Start time for the query. ISO format."),
    ] = None,
    end_time: Annotated[
        str | None,
        Query(description="End time for the query. ISO format."),
    ] = None,
    delta_time: Annotated[
        float,
        Query(
            description="Look-back number of seconds. "
            "Ignored if start_time/end_time are defined."
        ),
    ] = 3600,
    last: Annotated[
        bool,
        Query(description="Return only the last entry."),
    ] = False,
) -> list[dict]:
    """Returns the weather report from a weather station."""

    if start_time and end_time:
        df = await get_weather_data(
            station=station,
            start_time=start_time,
            end_time=end_time,
        )
    elif any([start_time, end_time]) and not all([start_time, end_time]):
        raise HTTPException(400, "start_time and end_time must be both defined.")
    else:
        df = await get_weather_data(station=station, start_time=delta_time)

    if last and len(df) > 0:
        df = df.tail(1)

    return df.with_columns(ts=polars.col.ts.dt.to_string("%FT%X")).to_dicts()
