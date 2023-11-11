#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: app.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI

from lvmapi.tools import CluClient


TELESCOPES_TYPE = Literal["sci", "spec", "skye", "skyw"]

app = FastAPI()


@app.get("/")
def root():
    return {}


@app.get("/telescopes/{telescope}/pointing")
async def get_pointing(
    telescope: TELESCOPES_TYPE,
    frame: Literal["radec", "altaz"] = "radec",
):
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
        ax0 = -999.0
        ax1 = -999.0

    if frame == "radec":
        return {"ra": ax0, "dec": ax1}
    else:
        return {"alt": ax0, "az": ax1}
