#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-09
# @Filename: notifications.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import datetime
import json
import re

from typing import Any, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from lvmopstools.notifications import NotificationLevel, send_notification
from sdsstools import get_sjd

from lvmapi import config
from lvmapi.tools.general import insert_to_database


__all__ = ["fill_notifications_mjd", "get_notifications", "create_notification"]


async def fill_notifications_mjd():
    """Fills MJD field for records in the notifications table.

    This is a temporary function to fill the MJD field in the notifications table and
    only needed due to a bug in the Overwatcher which was not filling the MJD field.

    """

    uri = config["database.uri"]
    table = Identifier(*config["database.tables.notification"].split("."))

    # Start by getting a list of records with null MJD.
    query = SQL("SELECT pk, date FROM {table} WHERE mjd IS NULL").format(table=table)
    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor() as acursor:
            await acursor.execute(query)
            records = await acursor.fetchall()

    for pk, date in records:
        sjd = get_sjd("LCO", date=date)
        query = SQL("UPDATE {table} SET mjd = %s WHERE pk = %s").format(table=table)
        async with await psycopg.AsyncConnection.connect(uri) as aconn:
            async with aconn.cursor() as acursor:
                await acursor.execute(query, (sjd, pk))
                await aconn.commit()


async def get_notifications(sjd: int | None = None):
    """Returns the notifications for an SJD."""

    sjd = sjd or get_sjd("LCO")

    uri = config["database.uri"]
    table = Identifier(*config["database.tables.notification"].split("."))

    query = SQL("""
        SELECT * FROM {table}
        WHERE mjd = %s AND message != %s ORDER BY date ASC
    """)

    async with await psycopg.AsyncConnection.connect(uri) as aconn:
        async with aconn.cursor(row_factory=dict_row) as acursor:
            await acursor.execute(query.format(table=table), (sjd, "I am alive!"))
            notifications = await acursor.fetchall()

    return notifications


def format_message_for_db(message: str) -> str:
    """Formats a message for storage in the database.

    Currently the only thing that is changed is replacing the Slack-flavoured
    link style (``<https://example.com|example>``) with a standard Markdown
    link format.

    """

    message = re.sub(
        r"(.*)<(.+)\|([\w\s]+)>",
        r"\1[\3](\2)",
        message,
        flags=re.ASCII | re.IGNORECASE,
    )

    return message


async def create_notification(
    message: str,
    payload: dict[str, Any] = {},
    level: NotificationLevel | str = NotificationLevel.INFO,
    slack: bool = True,
    slack_channels: str | Sequence[str] | None = None,
    email_on_critical: bool = True,
    slack_extra_params: dict[str, Any] = {},
    email_params: dict[str, Any] = {},
    write_to_database: bool = True,
):
    """Creates a new notification.

    Parameters
    ----------
    message
        The message of the notification. Can be formatted in Markdown.
    payload
        A dictionary with extra information to store with the notification.
        The payload is stored as a JSON string in the database and not emitted over
        Slack or email.
    level
        The level of the notification.
    slack
        Whether to send the notification to Slack.
    slack_channels
        The Slack channel where to send the notification. If not provided, the default
        channel is used. Can be set to false to disable sending the Slack notification.
    email_on_critical
        Whether to send an email if the notification level is ``CRITICAL``.
    slack_extra_params
        A dictionary of extra parameters to pass to ``post_message``.
    email_params
        A dictionary of extra parameters to pass to :obj:`.send_critical_error_email`.
    write_to_database
        Whether to write the notification to the database.

    Returns
    -------
    message
        The message that was sent.

    """

    if isinstance(level, str):
        level = NotificationLevel(level.upper())
    else:
        level = NotificationLevel(level)

    date = datetime.datetime.now()
    payload_str = json.dumps(payload)

    table = config["database.tables.notification"]

    message = await send_notification(
        message,
        level=level,
        slack=slack,
        slack_channels=slack_channels,
        email_on_critical=email_on_critical,
        slack_extra_params=slack_extra_params,
        email_params=email_params,
    )

    if write_to_database:
        message_db = format_message_for_db(message)

        # Was an email sent?
        email = email_on_critical and level == NotificationLevel.CRITICAL

        await insert_to_database(
            table,
            [
                {
                    "date": date,
                    "mjd": get_sjd("LCO", date=date),
                    "message": message_db,
                    "level": level.value.lower(),
                    "payload": payload_str,
                    "slack": slack,
                    "email": email,
                }
            ],
            columns=["date", "mjd", "message", "level", "payload", "slack", "email"],
        )
