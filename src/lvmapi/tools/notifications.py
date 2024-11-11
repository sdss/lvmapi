#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-11-09
# @Filename: notifications.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import datetime
import enum
import json
import pathlib
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from typing import Any, cast

import psycopg
from jinja2 import Environment, FileSystemLoader
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from sdsstools import get_sjd

from lvmapi import config
from lvmapi.tools.general import insert_to_database
from lvmapi.tools.slack import post_message


__all__ = ["get_notifications"]


class NotificationLevel(enum.Enum):
    """Allowed notification levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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
    level: NotificationLevel | str = NotificationLevel.INFO,
    payload: dict[str, Any] = {},
    slack_channel: str | bool | None = None,
    email_on_critical: bool = True,
    write_to_database: bool = True,
    slack_extra_params: dict[str, Any] = {},
):
    """Creates a new notification.

    Parameters
    ----------
    message
        The message of the notification. Can be formatted in Markdown.
    level
        The level of the notification.
    payload
        A dictionary with additional information to be stored with the notification.
        This data is not send over email or Slack, only stored in the database.
    slack_channel
        The Slack channel where to send the notification. If not provided, the default
        channel is used. Can be set to false to disable sending the Slack notification.
    email_on_critical
        Whether to send an email if the notification level is ``CRITICAL``.
    write_to_database
        Whether to write the notification to the database.
    slack_extra_params
        A dictionary of extra parameters to pass to ``post_message``.

    """

    date = datetime.datetime.now()
    payload_str = json.dumps(payload)

    if isinstance(level, str):
        level = NotificationLevel(level.upper())
    else:
        level = NotificationLevel(level)

    table = config["database.tables.notification"]

    slack = slack_channel is not False
    email = email_on_critical and level == NotificationLevel.CRITICAL

    if email:
        try:
            await send_critical_error_email(message)
        except Exception as ee:
            print(f"Error sending critical error email: {ee}")

    if slack_channel is not False:
        default_channel: str
        if slack_channel is None or slack_channel is True:
            default_channel = cast(str, config["slack.default_channel"])
        else:
            default_channel = slack_channel

        # We send the message to the default channel plus any other channel that
        # matches the level of the notification.
        channels: set[str] = {default_channel}

        level_channels = cast(dict[str, str], config["slack.level_channels"])
        if level.value in level_channels:
            channels.add(level_channels[level.value])

        # Send Slack message(s)
        for channel in channels:
            mentions = (
                ["@channel"]
                if level == NotificationLevel.CRITICAL
                or level == NotificationLevel.ERROR
                else []
            )
            await post_message(
                message,
                channel=channel,
                mentions=mentions,
                **slack_extra_params,
            )

    if write_to_database:
        message_db = format_message_for_db(message)
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


async def send_critical_error_email(message: str):
    """Sends a critical error email."""

    root = pathlib.Path(__file__).parents[1]
    template = root / config["notifications.critical.email_template"]
    loader = FileSystemLoader(template.parent)

    print(template, template.parent)

    env = Environment(
        loader=loader,
        lstrip_blocks=True,
        trim_blocks=True,
    )
    html_template = env.get_template(template.name)

    html_message = html_template.render(message=message.strip())

    recipients = config["notifications.critical.email_recipients"]
    from_address = config["notifications.critical.email_from"]

    email_server = config["notifications.critical.email_server"]
    email_host, *email_rest = email_server.split(":")
    email_port: int = 0
    if len(email_rest) == 1:
        email_port = int(email_rest[0])

    email_reply_to = config["notifications.critical.email_reply_to"]

    msg = MIMEMultipart("alternative" if html_message else "mixed")
    msg["Subject"] = "LVM Critical Alert"
    msg["From"] = from_address
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = email_reply_to

    plaintext_email = f"""A critical alert was raised in the LVM system.

The error message is shown below:

{message}

    """
    msg.attach(MIMEText(plaintext_email, "plain"))

    html = MIMEText(html_message, "html")
    msg.attach(html)

    with smtplib.SMTP(host=email_host, port=email_port) as smtp:
        smtp.sendmail(from_address, recipients, msg.as_string())
