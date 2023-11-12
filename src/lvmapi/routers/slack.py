#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import lvmapi.tools.slack


class Message(BaseModel):
    text: str
    channel: str | None = None


class MessageOut(BaseModel):
    text: str


router = APIRouter(prefix="/slack", tags=["slack"])


@router.get("/")
async def get_slack():
    """Not implemented."""

    return {}


@router.post(
    "/message",
    description="Send a message to Slack",
    response_model=MessageOut,
)
async def post_message(message: Message) -> Any:
    """Sends a message to the Slack channel."""

    try:
        await lvmapi.tools.slack.post_message(message.text, channel=message.channel)
    except Exception as err:
        raise HTTPException(500, detail=str(err))

    return message


@router.get("/message", description="Send a simple text message to Slack")
async def get_message(
    text: str = Query(description="Text to be sent"),
    channel: str | None = Query(None, description="Channel where to send the message"),
) -> str:
    """Sends a message to the Slack channel."""

    message: MessageOut = await post_message(Message(text=text, channel=channel))

    return message.text
