#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: slack.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

import lvmapi.tools.slack
from lvmapi import config


default_channel = config["slack.default_channel"]
default_user: str = "LVM"


class Message(BaseModel):
    text: Annotated[
        str | None,
        Field(description="Text to be sent"),
    ] = None

    blocks: Annotated[
        list[dict] | None,
        Field(description="Blocks of data to be sent"),
    ] = None

    attachments: Annotated[
        list[dict] | None,
        Field(description="Attachments to be sent"),
    ] = None

    channel: Annotated[
        str | None,
        Field(
            description="Channel where the message will be sent. "
            f"Defaults to {default_channel}."
        ),
    ] = None

    username: Annotated[
        str,
        Field(description="User that sends the message"),
    ] = default_user

    icon_url: Annotated[
        str | None,
        Field(description="URL for the icon to use"),
    ] = None

    mentions: Annotated[
        list[str],
        Field(description="List of user mentions"),
    ] = []

    @model_validator(mode="after")
    def validate_message(self):
        if self.text is None and self.blocks is None:
            raise ValueError("Must specify either text or blocks.")

        if self.text is not None and self.blocks is not None:
            raise ValueError("Cannot specify both text and blocks.")

        return self


router = APIRouter(prefix="/slack", tags=["slack"])


@router.get("/", summary="Slack API")
async def route_get_slack():
    """Not implemented."""

    return {}


@router.post("/message", summary="Send a message to Slack")
async def route_post_message(message: Message) -> None:
    """Sends a message to the Slack channel."""

    try:
        await lvmapi.tools.slack.post_message(
            message.text,
            blocks=message.blocks,
            channel=message.channel,
            username=message.username,
            icon_url=message.icon_url,
            mentions=message.mentions,
            attachments=message.attachments,
        )
    except Exception as err:
        raise HTTPException(500, detail=str(err))

    return None


@router.get("/message", summary="Send a simple text message to Slack")
async def route_get_message(
    text: str = Query(description="Text to be sent"),
    channel: str | None = Query(None, description="Channel where to send the message"),
    username: str = Query(default_user, description="Username to send the message as"),
    icon_url: str | None = Query(None, description="URL for the icon to use"),
    color: str | None = Query(None, description="Color of the message attachment"),
) -> None:
    """Sends a message to the Slack channel."""

    if color is not None:
        attachments = [
            {
                "color": color,
                "text": text,
                "mrkdwn_in": ["text"],
                "fallback": text,
            }
        ]
        text = ""
    else:
        attachments = []

    await route_post_message(
        Message(
            text=text,
            channel=channel,
            username=username,
            icon_url=icon_url,
            attachments=attachments,
        )
    )

    return None


@router.get("/user_id/{user}", summary="Gets the userID for a user name")
async def route_get_user_id(user: str) -> str | None:
    """Gets the ``userID`` of the user whose ``name`` or ``real_name`` matches."""

    try:
        user_id = await lvmapi.tools.slack.get_user_id(user)
    except NameError:
        return None
    except Exception as err:
        raise HTTPException(500, detail=str(err))

    return user_id
