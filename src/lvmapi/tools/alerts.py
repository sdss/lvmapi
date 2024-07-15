#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-12
# @Filename: alerts.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from lvmapi.tools.rabbitmq import CluClient
from lvmapi.tools.spectrograph import get_spectrograph_temperatures_history


__all__ = ["spec_temperature_alerts", "o2_alerts"]


async def spec_temperature_alerts(
    start: str = "-5m",
    ccd_threshold: float = -85,
    ln2_threshold: float = -175,
):
    """Returns a dictionary of spectrograph temperature alerts for each camera.

    Parameters
    ----------
    start
        How far back to query for spectrograph data. Must use the InfluxDB start time
        query format. The stop time for the query is always ``now()``.
    ccd_threshold
        The threshold for the CCD temperature. If the average temperature of the data
        returned for a camera is above this value, the camera is set as alerted.
    ln2_threshold
        As ``ccd_threshold`` for the LN2 can temperature.

    Returns
    -------
    temp_alerts_dict
        A dictionary of alerts. For each camera, the dictionary contains a boolean
        key for the CCD and LN2 temperature alerts, for example
        ``{'r1_ccd': False, 'r1_ln2': False, 'b1_ccd': True, ...}``.

    """

    temperatures = await get_spectrograph_temperatures_history(start)

    temp_alerts_dict: dict[str, bool] = {}

    for (camera, sensor), gg in temperatures.group_by(["camera", "sensor"]):
        if len(gg) == 0:
            temp_alerts_dict[f"{camera}_{sensor}"] = False
            continue

        mean_temp = float(gg["temperature"].to_numpy().mean())

        if sensor == "ccd":
            temp_alerts_dict[f"{camera}_ccd"] = mean_temp > ccd_threshold
        elif sensor == "ln2":
            temp_alerts_dict[f"{camera}_ln2"] = mean_temp > ln2_threshold

    return temp_alerts_dict


async def o2_alerts(threshold: float = 19.5):
    """Returns an alert if any of the O2 sensors is below the threshold.

    Parameters
    ----------
    threshold
        The threshold for the O2 level, as a percentage. If any of the sensors is
        below this value, the alert is raised.

    Returns
    -------
    o2_alerts_dict
        A dictionary of alerts. E.g.,
        ``{'o2_spec_room': False, 'o2_util_room': False}``.

    """

    async with CluClient() as client:
        status = await client.send_command(
            "lvmecp",
            "status",
            internal=True,
            time_limit=5,
        )

    if status.status.did_fail:
        raise ValueError("Failed retrieving status from ECP.")

    o2_alerts_dict = {
        "o2_spec_room": status.replies.get("o2_percent_spectrograph") < threshold,
        "o2_util_room": status.replies.get("o2_percent_utilities") < threshold,
    }

    return o2_alerts_dict
