#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-09
# @Filename: notifications.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import datetime

from typing import Annotated, Any, Sequence

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from sdsstools import get_sjd

from lvmapi.tools.notifications import (
    NotificationLevel,
    create_notification,
    get_notifications,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


class Notification(BaseModel):
    """An Overwatcher notification."""

    date: Annotated[
        datetime.datetime,
        Field(description="The notification datetime."),
    ]
    message: Annotated[
        str,
        Field(description="The notification message."),
    ]
    level: Annotated[
        str,
        Field(description="The level of the notification."),
    ]
    payload: Annotated[
        dict | None,
        Field(description="The payload of the notification."),
    ] = None


class NotificationPost(BaseModel):
    """Model for the ``/notifications/create`` endpoint payload."""

    message: Annotated[
        str,
        Field(description="The notification message."),
    ]
    level: Annotated[
        str,
        Field(description="The level of the notification."),
    ] = "INFO"
    payload: Annotated[
        dict[str, Any], Field(description="The payload of the notification.")
    ] = {}
    slack_channels: Annotated[
        str | Sequence[str] | None,
        Field(description="The Slack channel where to send the message."),
    ] = None
    slack: Annotated[
        bool,
        Field(description="Whether to send the notification to Slack."),
    ] = True
    email_on_critical: Annotated[
        bool, Field(description="Whether to send an email if the level is CRITICAL.")
    ] = True
    write_to_database: Annotated[
        bool, Field(description="Whether to write the notification to the database.")
    ] = True
    slack_extra_params: Annotated[
        dict[str, Any],
        Field(description="Extra parameters to pass to the Slack message."),
    ] = {}


@router.get("/{mjd}", summary="Returns notifications for an MJD.")
async def route_get_notifications(
    mjd: Annotated[
        int,
        Path(description="The SJD for which to list notifications. 0 for current SJD."),
    ],
) -> list[Notification]:
    """Returns a list of notifications for an MJD."""

    mjd = mjd if mjd > 0 else get_sjd("LCO")
    notifications = await get_notifications(mjd)

    return [
        Notification(**notification)
        for notification in notifications
        if notification["message"] != "I am alive!"
    ]


@router.post("/create", summary="Create a new notification.")
async def route_post_create_notification(notification: NotificationPost):
    """Creates a new notification, optionally emitting Slack and email messages."""

    try:
        await create_notification(
            notification.message,
            level=NotificationLevel(notification.level.upper()),
            payload=notification.payload,
            slack=notification.slack,
            slack_channels=notification.slack_channels,
            email_on_critical=notification.email_on_critical,
            write_to_database=notification.write_to_database,
            slack_extra_params=notification.slack_extra_params,
        )
    except Exception as ee:
        raise HTTPException(500, detail=str(ee))
