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

from lvmapi.tools.alerts import o2_alerts, spec_temperature_alerts


class AlertsSummary(BaseModel):
    """Summary of alerts."""

    ln2_alert: bool | None
    ln2_camera_alerts: dict[str, bool] | None
    o2_alert: bool | None
    heater_alert: bool | None
    heater_camera_alerts: dict[str, bool] | None


router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/")
@router.get("/summary")
async def summary() -> AlertsSummary:
    """Summary of alerts."""

    try:
        ln2_camera_alerts = await spec_temperature_alerts()
        ln2_alert = any(ln2_camera_alerts.values())
    except Exception as err:
        warnings.warn(f"Error getting temperature alerts: {err}")
        ln2_camera_alerts = None
        ln2_alert = None

    try:
        o2_camera_alerts = await o2_alerts()
        o2_alert = any(o2_camera_alerts.values())
    except Exception as err:
        warnings.warn(f"Error getting O2 level alerts: {err}")
        o2_alert = None

    return AlertsSummary(
        ln2_alert=ln2_alert,
        ln2_camera_alerts=ln2_camera_alerts,
        o2_alert=o2_alert,
        heater_alert=False,
        heater_camera_alerts={},
    )
