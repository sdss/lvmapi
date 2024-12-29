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

from lvmopstools.weather import get_weather_data, is_weather_data_safe

from lvmapi.cache import lvmapi_cache
from lvmapi.tools.alerts import enclosure_alerts, spec_temperature_alerts
from lvmapi.tools.general import is_host_up


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


class ConnectivityResponse(BaseModel):
    """Observatory connectivity status."""

    internet: bool
    lco: bool


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", summary="Summary of alerts")
@router.get("/", summary="Summary of alerts")
@router.get("/summary", summary="Summary of alerts")
@lvmapi_cache(expire=10)
async def route_get_summary():
    """Summary of alerts."""

    from lvmapi.app import app

    now = time.time()

    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(spec_temperature_alerts()))
    tasks.append(asyncio.create_task(enclosure_alerts()))
    tasks.append(asyncio.create_task(get_weather_data(start_time=now - 3600)))

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
        wind_alert = not is_weather_data_safe(
            weather_data,
            "wind_speed_avg",
            threshold=35,
            reopen_value=30,
        )

        humidity_alert = not is_weather_data_safe(
            weather_data,
            "relative_humidity",
            threshold=80,
            reopen_value=70,
        )

        last_weather = weather_data[-1]
        dew_point_alert = last_weather["dew_point"][0] > last_weather["temperature"][0]

    o2_alerts = {
        key: value for key, value in enclosure_alerts_response.items() if "o2_" in key
    }

    o2_alert = any(o2_alerts.values())
    rain_sensor_alarm = enclosure_alerts_response.get("rain_sensor_alarm", None)
    door_alert = enclosure_alerts_response.get("door_alert", None)

    # These fake states are just for testing.
    if app.state.use_fake_states:
        humidity_alert = app.state.fake_states["humidity_alert"]
        wind_alert = app.state.fake_states["wind_alert"]
        rain_sensor_alarm = app.state.fake_states["rain_alert"]
        door_alert = app.state.fake_states["door_alert"]

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


@router.get("/connectivity", summary="Observatory connectivity status")
async def route_get_connectivity():
    """Checks the connectivity of LVM to the outside world and other LCO networks."""

    internet = await is_host_up("8.8.8.8")  # Google DNS
    lco = await is_host_up("10.8.8.46")  # clima.lco.cl

    return ConnectivityResponse(internet=internet, lco=lco)
