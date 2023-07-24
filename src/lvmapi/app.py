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

from lvmapi.tools import Gort


TELESCOPES_TYPE = Literal["sci", "spec", "skye", "skyw"]

app = FastAPI()


@app.get("/")
def read_root():
    return {}


@app.get("/telescopes/{telescope}/pointing")
async def get_pointing(
    telescope: TELESCOPES_TYPE,
    frame: Literal["radec", "altaz"] = "radec",
):
    """Gets the pointing of a telescope."""

    try:
        async with Gort() as g:
            status = await g.telescopes[telescope].status()

        if frame == "radec":
            ax0 = status.get("ra_apparent_hours", -999 / 15) * 15
            ax1 = status.get("dec_apparent_degs", -999)
        elif frame == "altaz":
            ax0 = status.get("altitude_degs", -999)
            ax1 = status.get("azimuth_degs", -999)
        else:
            raise ValueError(f"Invalid frame {frame}")

    except Exception:
        ax0 = -999.0
        ax1 = -999.0

    if frame == "radec":
        return {"ra": ax0, "dec": ax1}
    else:
        return {"alt": ax0, "az": ax1}
