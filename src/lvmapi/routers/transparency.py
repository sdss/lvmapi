#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from datetime import datetime
from time import time

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from lvmapi.tools.transparency import get_transparency


router = APIRouter(prefix="/transparency", tags=["transparency"])


class TransparencyResponse(BaseModel):
    """Response model for transparency measurements."""

    start_time: Annotated[
        float,
        Field(description="Start time of the measurements as a UNIX timestamp"),
    ]
    end_time: Annotated[
        float,
        Field(description="End time of the measurements as a UNIX timestamp"),
    ]
    data: Annotated[
        list[TransparencyData],
        Field(description="Transparency data"),
    ]


class TransparencyData(BaseModel):
    """Model for transparency data."""

    time: Annotated[datetime, Field(description="Time of the measurement")]
    telescope: Annotated[str, Field(description="Telescope name")]
    zero_point: Annotated[float, Field(description="Zero-point value")]


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
) -> TransparencyResponse:
    """Returns transparency measurements.

    Without any parameters, returns the transparency measurements for the last hour.

    """

    if start_time is None or end_time is None:
        end_time = time()
        start_time = end_time - 3600

    data = await get_transparency(start_time, end_time)

    return TransparencyResponse(
        start_time=start_time,
        end_time=end_time,
        data=[TransparencyData(**row) for row in data.to_dicts()],
    )
