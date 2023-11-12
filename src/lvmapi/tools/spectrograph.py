#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-07-24
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

from lvmapi.tools.generic import CluClient
from lvmapi.types import Cameras, Sensors


if TYPE_CHECKING:
    from lvmapi.routers.spectrographs import Spectrographs


__all__ = [
    "get_spectrograph_temperature_label",
    "get_spectrograph_temperatures",
    "get_spectrograph_pressures",
    "get_spectrograph_mechanics",
]


def get_spectrograph_temperature_label(camera: str, sensor: str = "ccd"):
    """Returns the archon label associated with a temperature sensor."""

    if sensor == "ccd":
        if camera == "r":
            return "mod2/tempa"
        elif camera == "b":
            return "mod12/tempc"
        elif camera == "z":
            return "mod12/tempa"

    else:
        if camera == "r":
            return "mod2/tempb"
        elif camera == "b":
            return "mod2/tempc"
        elif camera == "z":
            return "mod12/tempb"


async def get_spectrograph_temperatures(spec: Spectrographs):
    """Returns a dictionary of spectrograph temperatures."""

    async with CluClient() as client:
        scp_command = await client.send_command(
            f"lvmscp.{spec}",
            "status",
            internal=True,
        )

    if scp_command.status.did_fail:
        raise ValueError("Failed retrieving status from SCP.")

    status = scp_command.replies.get("status")

    response: dict[str, float] = {}

    cameras: list[Cameras] = ["r", "b", "z"]
    sensors: list[Sensors] = ["ccd", "ln2"]

    for camera in cameras:
        for sensor in sensors:
            label = get_spectrograph_temperature_label(camera, sensor)
            if label not in status:
                raise ValueError(f"Cannot find status label {label!r}.")
            response[f"{camera}{spec[-1]}_{sensor}"] = status[label]

    return response


async def get_spectrograph_pressures(spec: Spectrographs):
    """Returns a dictionary of spectrograph pressures."""

    async with CluClient() as client:
        ieb_command = await client.send_command(
            f"lvmieb.{spec}",
            "transducer status",
            internal=True,
        )

    if ieb_command.status.did_fail:
        raise ValueError("Failed retrieving status from IEB.")

    pressures = ieb_command.replies.get("transducer")

    response: dict[str, float] = {}
    for key in pressures:
        if "pressure" in key:
            response[key] = pressures[key]

    return response


async def get_spectrograph_mechanics(spec: Spectrographs):
    """Returns a dictionary of spectrograph shutter and hartmann door status."""

    response: dict[str, str] = {}

    async with CluClient() as client:
        for device in ["shutter", "hartmann"]:
            ieb_cmd = await client.send_command(
                f"lvmieb.{spec}",
                f"{device} status",
                internal=True,
            )

            if ieb_cmd.status.did_fail:
                raise ValueError(f"Failed retrieving {device } status from IEB.")

            if device == "shutter":
                key = f"{spec}_shutter"
                response[key] = "open" if ieb_cmd.replies.get(key)["open"] else "closed"
            else:
                for door in ["left", "right"]:
                    key = f"{spec}_hartmann_{door}"
                    reply = ieb_cmd.replies.get(key)
                    response[key] = "open" if reply["open"] else "closed"

    return response
