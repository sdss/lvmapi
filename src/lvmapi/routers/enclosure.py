#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: enclosure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from lvmapi.tools.rabbitmq import send_clu_command


router = APIRouter(prefix="/enclosure", tags=["enclosure"])


class PLCStatus(BaseModel):
    """A model to represent a PLC sensor or function."""

    name: str
    value: int
    labels: list[str] = []

    @field_validator("value", mode="before")
    def cast_value(cls, value: str) -> int:
        return int(value, 16)

    @field_validator("labels", mode="after")
    def trim_labels(cls, value: list[str]) -> list[str]:
        return list(map(str.strip, value))


class O2Status(BaseModel):
    """Status of the O2 sensors."""

    utilities_room: float
    spectrograph_room: float


class EnclosureStatus(BaseModel):
    """A model to represent the status of the enclosure."""

    registers: dict[str, bool | float | int]

    dome_status: PLCStatus
    safety_status: PLCStatus
    lights_status: PLCStatus

    o2_status: O2Status


@router.get("/")
@router.get("/status")
async def status() -> EnclosureStatus:
    """Performs an emergency shutdown of the enclosure and telescopes."""

    try:
        ecp_status = await send_clu_command("lvmecp status")
    except Exception as ee:
        raise HTTPException(status_code=500, detail=str(ee))

    status_data: dict[str, Any] = {}
    for reply in ecp_status:
        if "registers" in reply:
            status_data["registers"] = reply["registers"]
        elif "dome_status" in reply:
            status_data["dome_status"] = {
                "name": "dome",
                "value": reply["dome_status"],
                "labels": reply["dome_status_labels"].split(","),
            }
        elif "lights" in reply:
            status_data["lights_status"] = {
                "name": "lights",
                "value": reply["lights"],
                "labels": reply["lights_labels"].split(","),
            }
        elif "safety_status" in reply:
            status_data["safety_status"] = {
                "name": "safety",
                "value": reply["safety_status"],
                "labels": reply["safety_status_labels"].split(","),
            }
        elif "o2_percent_utilities" in reply:
            status_data["o2_status"] = {
                "utilities_room": reply["o2_percent_utilities"],
                "spectrograph_room": reply["o2_percent_spectrograph"],
            }

    return EnclosureStatus(**status_data)
