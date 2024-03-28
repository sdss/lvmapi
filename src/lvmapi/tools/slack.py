#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from lvmapi import config


__all__ = ["post_message"]


async def post_message(text: str, channel: str | None = None, **kwargs):
    token = config["slack.token"] or os.environ["SLACK_API_TOKEN"]

    channel = channel or config["slack.channel"]
    assert channel is not None

    client = AsyncWebClient(token=token)

    try:
        await client.chat_postMessage(channel=channel, text=text, **kwargs)
    except SlackApiError as e:
        raise RuntimeError(f"Slack returned an error: {e.response['error']}")
