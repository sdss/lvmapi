#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: telescopes.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio

from typing import get_args

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lvmapi.auth import AuthDependency
from lvmapi.tasks import park_telescopes_task
from lvmapi.tools import CluClient
from lvmapi.tools.telescopes import get_telescope_status
from lvmapi.types import Coordinates, Telescopes


class PointingResponse(BaseModel):
    """Response model for telescope pointing."""

    ra: float = Field(description="Right Ascension in degrees")
    dec: float = Field(description="Declination in degrees")
    alt: float = Field(description="Altitude in degrees")
    az: float = Field(description="Azimuth in degrees")


class TelescopeStatusResponse(BaseModel):
    """Response model for telescope status."""

    reachable: bool = Field(
        description="Whether the telescope is reachable",
    )
    ra: float | None = Field(
        default=None,
        description="Right Ascension in degrees",
    )
    dec: float | None = Field(
        default=None,
        description="Declination in degrees",
    )
    alt: float | None = Field(
        default=None,
        description="Altitude in degrees",
    )
    az: float | None = Field(
        default=None,
        description="Azimuth in degrees",
    )
    is_tracking: bool | None = Field(
        default=None,
        description="Whether the telescope is tracking",
    )
    is_connected: bool | None = Field(
        default=None,
        description="Whether the telescope is connected",
    )
    is_slewing: bool | None = Field(
        default=None,
        description="Whether the telescope is slewing",
    )
    is_enabled: bool | None = Field(
        default=None,
        description="Whether the telescope is enabled",
    )


router = APIRouter(prefix="/telescopes", tags=["telescopes"])


@router.get("/", summary="List of telescopes")
async def route_get_telescopes() -> list[str]:
    """Returns the list of telescopes."""

    return list(get_args(Telescopes))


@router.get("/coordinates", summary="Pointing of al ltelescopes")
async def route_get_coordinates() -> dict[str, PointingResponse]:
    """Gets the pointings of all telescopes."""

    telescopes = get_args(Telescopes)
    pointings = await asyncio.gather(*[route_get_pointing(tel) for tel in telescopes])

    return {tel: pointing for tel, pointing in zip(telescopes, pointings)}


@router.get(
    "/{telescope}/pointing",
    summary="Telescope pointing",
    response_model=PointingResponse,
)
async def route_get_pointing(telescope: Telescopes) -> PointingResponse:
    """Gets the pointing of a telescope."""

    try:
        async with CluClient() as client:
            status_cmd = await client.send_command(f"lvm.{telescope}.pwi", "status")

        ra = status_cmd.replies.get("ra_apparent_hours") * 15
        dec = status_cmd.replies.get("dec_apparent_degs")
        alt = status_cmd.replies.get("altitude_degs")
        az = status_cmd.replies.get("azimuth_degs")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error retrieving telescope information.",
        )

    return PointingResponse(ra=ra, dec=dec, alt=alt, az=az)


@router.get("/{telescope}/{coordinate}", summary="Telescope coordinates")
async def route_get_tel_coord(telescope: Telescopes, coordinate: Coordinates) -> float:
    """Returns a given coordinate for a telescope."""

    pointing = await route_get_pointing(telescope)
    return getattr(pointing, coordinate)


@router.get("/status", summary="Telescope status")
async def route_get_telescope_status():
    """Gets the status of all telescopes."""

    status = await asyncio.gather(
        *[get_telescope_status(tel) for tel in get_args(Telescopes)],
        return_exceptions=True,
    )

    response: dict[Telescopes, TelescopeStatusResponse] = {}
    for tel, stat in zip(get_args(Telescopes), status):
        if isinstance(stat, BaseException):
            response[tel] = TelescopeStatusResponse(reachable=False)
        else:
            response[tel] = TelescopeStatusResponse(reachable=True, **stat)

    return response


@router.get("/parked", summary="Are telescopes parked?")
async def route_get_parked() -> dict[Telescopes, bool | None]:
    """Returns whether the telescopes are parked or not."""

    park_position = (-60, 90)
    status = await route_get_telescope_status()

    response: dict[Telescopes, bool | None] = {}
    for telescope, status in status.items():
        if (
            not status.reachable
            or not status.is_connected
            or not status.alt
            or not status.az
        ):
            response[telescope] = None
        else:
            if status.is_slewing or status.is_tracking:
                response[telescope] = False
            else:
                alt_diff = abs(status.alt - park_position[0])
                az_diff = abs(status.az - park_position[1])

                if alt_diff > 5 or az_diff > 5:
                    response[telescope] = False
                else:
                    response[telescope] = True

    return response


@router.get("/park", summary="Park all telescopes", dependencies=[AuthDependency])
async def route_park_telescopes() -> str:
    """Parks all telescopes. Scheduled as a task."""

    task = await park_telescopes_task.kiq()

    return task.task_id
