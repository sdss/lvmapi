#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2025-02-26
# @Filename: system.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import re

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from lvmopstools.utils import is_host_up

from lvmapi import config


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ping/{host}", summary="Pings a host or device")
async def get_route_ping(
    host: Annotated[str, Path(description="The host or device to ping")],
) -> bool:
    """Pings a host or device."""

    is_ip = re.match(r"^\d{1,3}\.\d{0,3}\.\d{1,3}\.\d{1,3}$", host)

    if not is_ip:
        if host not in config["hosts"] or config["hosts"][host] is None:
            raise HTTPException(status_code=400, detail="Invalid or unknown device.")
        host = config["hosts"][host]

    try:
        return await is_host_up(host)
    except Exception as ee:
        raise HTTPException(status_code=500, detail=f"Failed pinging device: {ee}")
