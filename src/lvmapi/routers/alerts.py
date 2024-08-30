#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-10
# @Filename: alerts.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import time
import warnings

import polars
from fastapi import APIRouter
from pydantic import BaseModel

from lvmapi.tools.alerts import enclosure_alerts, spec_temperature_alerts
from lvmapi.tools.weather import get_weather_data


class AlertsSummary(BaseModel):
    """Summary of alerts."""

    humidity_alert: bool | None = None
    dew_point_alert: bool | None = None
    wind_alert: bool | None = None
    rain: bool | None = None
    door_alert: bool | None = None
    camera_temperature_alert: bool | None = None
    camera_alerts: dict[str, bool] | None = None
    o2_alert: bool | None = None
    o2_room_alerts: dict[str, bool] | None = None
    heater_alert: bool | None = None
    heater_camera_alerts: dict[str, bool] | None = None


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/")
@router.get("/summary")
async def summary() -> AlertsSummary:
    """Summary of alerts."""

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(spec_temperature_alerts()))
    tasks.append(asyncio.create_task(enclosure_alerts()))
    tasks.append(asyncio.create_task(get_weather_data(start_time=3600)))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    camera_alerts = results[0]
    if isinstance(camera_alerts, BaseException):
        warnings.warn(f"Error getting temperature alerts: {camera_alerts}")
        camera_alerts = None
        camera_temperature_alert = None
    else:
        camera_temperature_alert = any(camera_alerts.values())

    enclosure_alerts_response = results[1]
    if isinstance(enclosure_alerts_response, BaseException):
        enclosure_alerts_response = {}

    weather_data: polars.DataFrame | BaseException = results[2]

    wind_alert = None
    humidity_alert = None
    dew_point_alert = None

    if not isinstance(weather_data, BaseException) and weather_data.height > 0:
        last_weather = weather_data[-1]

        humidity_alert = last_weather["relative_humidity"][0] > 80
        dew_point_alert = last_weather["dew_point"][0] > last_weather["temperature"][0]

        now = time.time()
        last_30m = weather_data.filter(polars.col.ts.dt.timestamp("ms") > (now - 1800))

        # LCO rules are to close if wind speed is above 35 mph in the 30 minute
        # average and reopen only if the average is below 30 mph.
        wind_30m_last = last_weather["wind_speed_avg_30m"][0]
        if wind_30m_last > 35:
            wind_alert = True
        elif wind_30m_last < 30:
            wind_alert = False
        else:
            if (last_30m["wind_speed_avg_30m"] > 35).any():
                wind_alert = True
            else:
                wind_alert = False

    o2_alerts = {
        key: value for key, value in enclosure_alerts_response.items() if "o2_" in key
    }

    o2_alert = any(o2_alerts.values())
    rain_sensor_alarm = enclosure_alerts_response.get("rain_sensor_alarm", None)
    door_alert = enclosure_alerts_response.get("door_alert", None)

    return AlertsSummary(
        humidity_alert=humidity_alert,
        dew_point_alert=dew_point_alert,
        rain=rain_sensor_alarm,
        door_alert=door_alert,
        wind_alert=wind_alert,
        camera_temperature_alert=camera_temperature_alert,
        camera_alerts=camera_alerts,
        heater_alert=False,
        heater_camera_alerts={},
        o2_alert=o2_alert,
        o2_room_alerts=o2_alerts,
    )
