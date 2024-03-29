#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, model_validator

import lvmapi.tools.slack


class Message(BaseModel):
    text: str
    blocks: list[dict] | None = None
    channel: str | None = None
    username: str | None = None
    icon_url: str | None = None
    mentions: list[str] = []

    @model_validator(mode="after")
    def validate_message(self):
        if self.text is None and self.blocks is None:
            raise ValueError("Must specify either text or blocks.")

        if self.text is not None and self.blocks is not None:
            raise ValueError("Cannot specify both text and blocks.")

        return self


router = APIRouter(prefix="/slack", tags=["slack"])


@router.get("/")
async def get_slack():
    """Not implemented."""

    return {}


@router.post("/message", description="Send a message to Slack")
async def post_message(message: Message) -> None:
    """Sends a message to the Slack channel."""

    try:
        await lvmapi.tools.slack.post_message(
            message.text,
            blocks=message.blocks,
            channel=message.channel,
            username=message.username,
            icon_url=message.icon_url,
            mentions=message.mentions,
        )
    except Exception as err:
        raise HTTPException(500, detail=str(err))

    return None


@router.get("/message", description="Send a simple text message to Slack")
async def get_message(
    text: str = Query(description="Text to be sent"),
    channel: str | None = Query(None, description="Channel where to send the message"),
    username: str | None = Query(None, description="Username to send the message as"),
    icon_url: str | None = Query(None, description="URL for the icon to use"),
) -> None:
    """Sends a message to the Slack channel."""

    await post_message(
        Message(
            text=text,
            channel=channel,
            username=username,
            icon_url=icon_url,
        )
    )

    return None


@router.get("/user_id/{user}", description="Gets the userID for a user name")
async def get_user_id(user: str) -> str | None:
    """Gets the ``userID`` of the user whose ``name`` or ``real_name`` matches."""

    try:
        user_id = await lvmapi.tools.slack.get_user_id(user)
    except NameError:
        return None
    except Exception as err:
        raise HTTPException(500, detail=str(err))

    return user_id
