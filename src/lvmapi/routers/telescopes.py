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
from pydantic import BaseModel

from lvmapi.tools import CluClient
from lvmapi.types import Coordinates, Telescopes


class PointingResponse(BaseModel):
    ra: float
    dec: float
    alt: float
    az: float


router = APIRouter(prefix="/telescopes", tags=["telescopes"])


@router.get("/", summary="List of telescopes")
async def get_telescopes() -> list[str]:
    """Returns the list of telescopes."""

    return list(get_args(Telescopes))


@router.get("/coordinates", summary="Pointing of al ltelescopes")
async def get_allpointings() -> dict[str, PointingResponse]:
    """Gets the pointings of all telescopes."""

    telescopes = get_args(Telescopes)
    pointings = await asyncio.gather(*[get_pointing(tel) for tel in telescopes])

    return {tel: pointing for tel, pointing in zip(telescopes, pointings)}


@router.get(
    "/{telescope}/pointing",
    summary="Telescope pointing",
    response_model=PointingResponse,
)
async def get_pointing(telescope: Telescopes) -> PointingResponse:
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
async def get_ra(telescope: Telescopes, coordinate: Coordinates) -> float:
    """Returns a given coordinate for a telescope."""

    pointing = await get_pointing(telescope)
    return getattr(pointing, coordinate)
