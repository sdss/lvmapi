#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-06-14
# @Filename: enclosure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import enum

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel, Field, create_model, field_validator

from lvmopstools.devices import read_nps
from sdsstools.utils import GatheringTaskGroup

from lvmapi.auth import AuthDependency
from lvmapi.tasks import move_dome_task
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

    cal_lamp_state: dict[str, bool]


class Lights(enum.Enum):
    control_room = "control_room"
    spectrograph_room = "spectrograph_room"
    utilities_room = "utilities_room"
    uma_room = "uma_room"
    telescope_bright = "telescope_bright"
    telescope_red = "telescope_red"
    all = "all"


LightsStatus: type[BaseModel] = create_model(
    "LightsStatus",
    __doc__="Model of lights status",
    **{light: (bool, False) for light in Lights.__members__ if light != "all"},  # type: ignore
)


class NPSBody(BaseModel):
    """Model for NPS data."""

    outlet: Annotated[str, Field(description="The outlet to control or 'all'.")]
    state: Annotated[bool, Field(description="The state to set (on/off).")]


@router.get("")
@router.get("/")
@router.get("/status")
async def status() -> EnclosureStatus:
    """Performs an emergency shutdown of the enclosure and telescopes."""

    try:
        async with GatheringTaskGroup() as group:
            group.create_task(send_clu_command("lvmecp status"))
            group.create_task(route_get_nps(nps="calib"))

        ecp_status, cal_lamp_state = group.results()
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

    return EnclosureStatus(**status_data, cal_lamp_state=cal_lamp_state)


@router.get("/open", dependencies=[AuthDependency])
async def open_enclosure():
    """Opens the enclosure. Scheduled as a task."""

    task = await move_dome_task.kiq(direction="open")
    return task.task_id


@router.get("/close", dependencies=[AuthDependency])
async def close_enclosure(force: bool = False):
    """Closes the enclosure. Scheduled as a task."""

    task = await move_dome_task.kiq(direction="close", force=force)
    return task.task_id


@router.get("/stop", dependencies=[AuthDependency])
async def stop_enclosure():
    """Stops the enclosure."""

    try:
        await send_clu_command("lvmecp dome stop")
    except Exception as ee:
        raise HTTPException(status_code=500, detail=str(ee))

    return True


@router.get("/lights", response_model=LightsStatus)
async def get_lights():
    """Returns the status of the lights."""

    try:
        ecp_status = await send_clu_command("lvmecp lights")
    except Exception as ee:
        raise HTTPException(status_code=500, detail=str(ee))

    lights = ecp_status[0]["lights_labels"]

    response_dict: dict[str, bool] = {}
    for light in lights:
        response_dict[light.lower()] = True

    return LightsStatus(**response_dict)


@router.get("/lights/{mode}/{lamp}", dependencies=[AuthDependency])
async def set_lights(
    mode: Literal["on", "off"],
    lamp: Annotated[
        Lights,
        Path(
            description="The lamp to turn on/off. Can also be 'all' (only allowed "
            "with mode='off').",
        ),
    ],
):
    """Turns a lamp on/off."""

    lamp_str = lamp.value

    if mode == "on" or (mode == "off" and lamp_str != "all"):
        if lamp_str == "all":
            raise HTTPException(
                status_code=400,
                detail="Lamp must be specified when turning lights on.",
            )
        await send_clu_command(f"lvmecp lights {mode} {lamp_str}")

    else:
        await asyncio.gather(
            *[
                send_clu_command(f"lvmecp lights off {lamp}")
                for lamp in Lights.__members__
                if lamp != "all"
            ]
        )


@router.get("/nps/{nps}", summary="Reads an NPS")
async def route_get_nps(
    nps: Annotated[str, Path(description="The NPS for which to return the data.")],
) -> dict[str, bool]:
    """Returns the state of a network power switch."""

    try:
        nps_data = await read_nps()
    except Exception as ee:
        raise HTTPException(500, detail=str(ee))

    return {
        outlet.split(".")[1]: nps_data[outlet]["state"]
        for outlet in nps_data
        if outlet.split(".")[0] == nps
    }


@router.put("/nps/{nps}", summary="Sets an NPS switch")
async def route_put_nps(
    nps: Annotated[
        Literal["calib"],
        Path(description="The NPS for which to set the data."),
    ],
    data: Annotated[
        NPSBody,
        Body(description="The NPS data to set."),
    ],
) -> bool:
    """Sets the state of an NPS outlet."""

    command = "on" if data.state else "off"

    try:
        if data.outlet == "all":
            if data.state:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot turn all outlets on.",
                )
            await send_clu_command(f"lvmnps.{nps} all-off")
        else:
            await send_clu_command(f"lvmnps.{nps} {command} {data.outlet}")
    except RuntimeError:
        return False

    return True
