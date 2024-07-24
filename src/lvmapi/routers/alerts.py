#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-10
# @Filename: alerts.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import warnings

from fastapi import APIRouter
from pydantic import BaseModel

from lvmapi.tools.alerts import enclosure_alerts, spec_temperature_alerts


class AlertsSummary(BaseModel):
    """Summary of alerts."""

    temperature_alert: bool | None = None
    camera_alerts: dict[str, bool] | None = None
    o2_alert: bool | None = None
    o2_room_alerts: dict[str, bool] | None = None
    heater_alert: bool | None = None
    heater_camera_alerts: dict[str, bool] | None = None
    rain: bool | None = None
    door_alert: bool | None = None


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/")
@router.get("/summary")
async def summary() -> AlertsSummary:
    """Summary of alerts."""

    try:
        camera_alerts = await spec_temperature_alerts()
        temperature_alert = any(camera_alerts.values())
    except Exception as err:
        warnings.warn(f"Error getting temperature alerts: {err}")
        camera_alerts = None
        temperature_alert = None

    try:
        enclosure_alerts_response = await enclosure_alerts()
    except Exception as err:
        warnings.warn(f"Error getting enclosure alerts: {err}")
        enclosure_alerts_response = {}

    o2_alerts = {
        key: value for key, value in enclosure_alerts_response.items() if "o2_" in key
    }

    o2_alert = any(o2_alerts.values())
    rain_sensor_alarm = enclosure_alerts_response.get("rain_sensor_alarm", None)
    door_alert = enclosure_alerts_response.get("door_alert", None)

    return AlertsSummary(
        temperature_alert=temperature_alert,
        camera_alerts=camera_alerts,
        o2_alert=o2_alert,
        o2_room_alerts=o2_alerts,
        heater_alert=False,
        heater_camera_alerts={},
        rain=rain_sensor_alarm,
        door_alert=door_alert,
    )
