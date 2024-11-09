#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os
import re

from typing import Sequence

from aiocache import cached
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from lvmapi import config


__all__ = ["post_message", "get_user_id"]


def get_api_client(token: str | None = None):
    """Gets a Slack API client."""

    token = token or config["slack.token"] or os.environ["SLACK_API_TOKEN"]

    return AsyncWebClient(token=token)


async def format_mentions(text: str | None, mentions: list[str]) -> str | None:
    """Formats a text message with mentions."""

    if not text:
        return text

    if len(mentions) > 0:
        for mention in mentions[::-1]:
            if mention[0] != "@":
                mention = f"@{mention}"
            if mention not in text:
                text = f"{mention} {text}"

    # Replace @channel, @here, ... with the API format <!here>.
    text = re.sub(r"(\s|^)@(here|channel|everone)(\s|$)", r"\1<!here>\3", text)

    # The remaining mentions should be users. But in the API these need to be
    # <@XXXX> where XXXX is the user ID and not the username.
    users: list[str] = re.findall(r"(?:\s|^)@([a-zA-Z_]+)(?:\s|$)", text)

    for user in users:
        try:
            user_id = await get_user_id(user)
        except NameError:
            continue
        text = text.replace(f"@{user}", f"<@{user_id}>")

    return text


async def post_message(
    text: str | None = None,
    blocks: Sequence[dict] | None = None,
    channel: str | None = None,
    mentions: list[str] = [],
    **kwargs,
):
    """Posts a message to Slack.

    Parameters
    ----------
    text
        Plain text to send to the Slack channel.
    blocks
        A list of blocks to send to the Slack channel. These follow the Slack
        API format for blocks. Incompatible with ``text``.
    channel
        The channel in the SSDS-V workspace where to send the message.
    mentions
        A list of users to mention in the message.

    """

    if text is None and blocks is None:
        raise ValueError("Must specify either text or blocks.")

    if text is not None and blocks is not None:
        raise ValueError("Cannot specify both text and blocks.")

    channel = channel or config["slack.default_channel"]
    assert channel is not None

    client = get_api_client()

    try:
        text = await format_mentions(text, mentions)
        await client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks,
            **kwargs,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack returned an error: {e.response['error']}")


@cached(ttl=120)
async def get_user_list():
    """Returns the list of users in the workspace.

    This function is cached because Slack limits the requests for this route.

    """

    client = get_api_client()

    try:
        users_list = await client.users_list()
        if users_list["ok"] is False:
            err = "users_list returned ok=false"
            raise SlackApiError(err, response={"error": err})

        return users_list

    except SlackApiError as e:
        raise RuntimeError(f"Slack returned an error: {e.response['error']}")


async def get_user_id(name: str):
    """Gets the ``userID`` of the user display name matches ``name``."""

    users_list = await get_user_list()

    for member in users_list["members"]:
        if "profile" not in member or "display_name" not in member["profile"]:
            continue

        if (
            member["profile"]["display_name"] == name
            or member["profile"]["display_name_normalized"] == name
        ):
            return member["id"]

    raise NameError(f"User {name} not found.")
