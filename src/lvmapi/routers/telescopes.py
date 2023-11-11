#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: telescopes.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from lvmapi.tools import CluClient


Telescopes = Literal["sci", "spec", "skye", "skyw"]
Frames = Literal["radec", "altaz"]
Coordinates = Literal["ra", "dec", "alt", "az"]


router = APIRouter(prefix="/telescopes", tags=["telescopes"])


@router.get("/{telescope}/pointing")
async def get_pointing(telescope: Telescopes, frame: Frames = "radec"):
    """Gets the pointing of a telescope."""

    try:
        async with CluClient() as client:
            status_cmd = await client.send_command(f"lvm.{telescope}.pwi", "status")

        if frame == "radec":
            ax0 = status_cmd.replies.get("ra_apparent_hours") * 15
            ax1 = status_cmd.replies.get("dec_apparent_degs")
        elif frame == "altaz":
            ax0 = status_cmd.replies.get("altitude_degs")
            ax1 = status_cmd.replies.get("azimuth_degs")
        else:
            raise ValueError(f"Invalid frame {frame}")

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Error retrieving telescope information.",
        )

    if frame == "radec":
        return {"ra": ax0, "dec": ax1}
    else:
        return {"alt": ax0, "az": ax1}


@router.get("/{telescope}/{coordinate}")
async def get_ra(telescope: Telescopes, coordinate: Coordinates):
    """Returns a given coordinate for a telescope."""

    frame = "radec" if coordinate in ["ra", "dec"] else "altaz"

    pointing = await get_pointing(telescope, frame=frame)
    return pointing[coordinate]
