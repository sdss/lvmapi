#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-11
# @Filename: transparency.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import enum
from datetime import datetime
from time import time

from typing import Annotated, Literal, cast

import polars
from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from lvmapi.tools.transparency import get_transparency


router = APIRouter(prefix="/transparency", tags=["transparency"])


class TransparencyDataResponse(BaseModel):
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

    date: Annotated[datetime, Field(description="Time of the measurement")]
    timestamp: Annotated[float, Field(description="UNIX timestamp of the measurement")]
    telescope: Annotated[str, Field(description="Telescope name")]
    zero_point: Annotated[float, Field(description="Zero-point value")]


class TransparencyQuality(enum.Enum):
    """Quality of the transparency data."""

    GOOD = "good"
    BAD = "bad"
    POOR = "poor"
    UNKNOWN = "unknown"


class TransparencyTrend(enum.Enum):
    """Trend of the transparency data."""

    IMPROVING = "improving"
    WORSENING = "worsening"
    FLAT = "flat"


class TransparencySummaryResponse(BaseModel):
    """Response model for transparency summary."""

    telescope: Annotated[str, Field(description="Telescope name")]
    mean_zp: Annotated[float | None, Field(description="Mean zero-point value")]
    quality: Annotated[TransparencyQuality, Field(description="Transparency quality")]
    trend: Annotated[TransparencyTrend, Field(description="Transparency trend")]


Telescope = Literal["sci", "spec", "skye", "skyw"]


@router.get("", summary="Transparency measurements")
async def route_get_transparency(
    start_time: Annotated[
        float | None,
        Query(description="Start time as a UNIX timestamp"),
    ] = None,
    end_time: Annotated[
        float | None,
        Query(description="End time as a UNIX timestamp"),
    ] = None,
) -> TransparencyDataResponse:
    """Returns transparency measurements.

    Without any parameters, returns the transparency measurements for the last hour.

    """

    if start_time is None or end_time is None:
        end_time = time()
        start_time = end_time - 3600

    data = await get_transparency(start_time, end_time)

    return TransparencyDataResponse(
        start_time=start_time,
        end_time=end_time,
        data=[TransparencyData(**row) for row in data.to_dicts()],
    )


@router.get("/summary/{telescope}")
async def route_get_transparency_summary(
    telescope: Annotated[Telescope, Path(description="Telescope name")],
) -> TransparencySummaryResponse:
    """Returns a summary of the transparency for a telescope in the last 15 minutes."""

    now = time()
    data = await get_transparency(now - 900, now)

    data_tel = data.filter(polars.col.telescope == telescope)

    if len(data_tel) < 5:
        return TransparencySummaryResponse(
            telescope=telescope,
            mean_zp=None,
            quality=TransparencyQuality.UNKNOWN,
            trend=TransparencyTrend.FLAT,
        )

    # Add a rolling mean.
    data_tel = data_tel.with_columns(
        zero_point_10m=polars.col.zero_point.rolling_mean_by(
            by="date",
            window_size="10m",
        ).over("telescope")
    )

    data_tel_5m = data_tel.filter(polars.col.timestamp > now - 300)
    mean_zp: float | None = None
    if len(data_tel_5m) > 0:
        mean_zp = cast(float, data_tel_5m["zero_point"].mean())
    else:
        mean_zp = cast(float, data_tel["zero_point"].mean())

    quality: TransparencyQuality = TransparencyQuality.UNKNOWN
    trend: TransparencyTrend = TransparencyTrend.FLAT

    if mean_zp is None:
        pass
    elif mean_zp < -22.75:
        quality = TransparencyQuality.GOOD
    elif mean_zp > -22.75 and mean_zp < -22.25:
        quality = TransparencyQuality.POOR
    else:
        quality = TransparencyQuality.BAD

    zp_tel = data_tel["zero_point_10m"].to_numpy()
    time_tel = data_tel["timestamp"].to_numpy()
    gradient = (zp_tel[-1] - zp_tel[0]) / (time_tel[-1] - time_tel[0])

    if gradient > 5e-4:
        trend = TransparencyTrend.WORSENING
    elif gradient < -5e-4:
        trend = TransparencyTrend.IMPROVING

    return TransparencySummaryResponse(
        telescope=telescope,
        mean_zp=round(mean_zp, 2) if mean_zp is not None else None,
        quality=quality,
        trend=trend,
    )
