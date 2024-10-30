#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Body, Path, Query
from pydantic import BaseModel, Field

from sdsstools import get_sjd

from lvmapi.tasks import get_exposure_data_task
from lvmapi.tools.logs import (
    add_night_log_comment,
    create_night_log_entry,
    delete_night_log_comment,
    email_night_log,
    get_exposure_data,
    get_exposure_table_ascii,
    get_exposures,
    get_night_log_data,
    get_night_log_mjds,
    get_plaintext_night_log,
    get_spectro_mjds,
)


class NightLogComment(BaseModel):
    """A comment in the night log."""

    pk: Annotated[int, Field(description="The primary key of the comment")]
    date: Annotated[datetime, Field(description="The time the comment was loaded")]
    comment: Annotated[str, Field(description="The comment text")]


class NightLogData(BaseModel):
    """The night log data for an MJD."""

    mjd: Annotated[
        int,
        Field(description="The MJD associated with the comments"),
    ]
    current: Annotated[
        bool,
        Field(description="Whether the night log is for the current MJD"),
    ]
    exists: Annotated[
        bool,
        Field(description="Whether the night log exists in the DB"),
    ]
    sent: Annotated[
        bool,
        Field(description="Whether the night log has been sent"),
    ] = False
    observers: Annotated[
        str | None,
        Field(description="The observers that took the data"),
    ] = None
    comments: Annotated[
        dict[str, list[NightLogComment]],
        Field(description="The list of comments, organised by category"),
    ] = {}
    exposure_table: Annotated[
        str | None,
        Field(description="The exposure table for the night log"),
    ] = None


class NightLogPostComment(BaseModel):
    """A comment to add to the night log."""

    mjd: Annotated[
        int,
        Field(description="The MJD associated with the comment"),
    ]
    category: Annotated[
        str,
        Field(description="The category of the comment"),
    ]
    comment: Annotated[
        str,
        Field(description="The comment text"),
    ]
    pk: Annotated[
        int | None,
        Field(
            description="The primary key of the comment. If provided, "
            "the comment will be updated."
        ),
    ] = None


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("/")
async def route_get_log():
    """Not implemented."""

    return {}


@router.get("/exposures/mjds", summary="List of MJDs with spectrograph data")
async def route_get_spectro_mjds():
    """Returns a list of MJDs with spectrograph data (or at least a folder)."""

    mjds = await asyncio.get_event_loop().run_in_executor(None, get_spectro_mjds)
    return mjds


@router.get(
    "/exposures/data/{mjd}",
    summary="Returns data from exposures for an MJD.",
)
async def route_get_exposures_data(
    mjd: Annotated[
        int,
        Path(description="The SJD (Sloan-flavoured MJD) for which to list exposures."),
    ],
    as_task: Annotated[
        bool,
        Query(description="Whether to schedule this as a task."),
    ] = False,
):
    """Returns a log of exposures for an MJD.."""

    if as_task is False:
        executor = asyncio.get_event_loop().run_in_executor
        exposure_data = await executor(None, get_exposure_data, mjd)
        return exposure_data

    task = await get_exposure_data_task.kiq(mjd)
    return task.task_id


@router.get("/exposures/{mjd}", summary="Returns a list of exposures for an MJD.")
async def route_get_exposures(
    mjd: Annotated[
        int,
        Path(description="The SJD (Sloan-flavoured MJD) for which to list exposures."),
    ],
):
    """Returns a list of exposures for an MJD."""

    executor = asyncio.get_event_loop().run_in_executor
    exposures = await executor(None, get_exposures, mjd)

    return list(map(str, exposures))


@router.get("/night-logs", summary="List of night log MJDs.")
async def route_get_night_logs():
    """Returns a list of MJDs with night log data."""

    mjds = await get_night_log_mjds()
    return mjds


@router.get("/night-logs/create", summary="Create night log entry")
async def route_get_night_logs_create():
    """Creates a night log entry for the current MJD."""

    mjd = await create_night_log_entry()
    return mjd


@router.post("/night-logs/comments/add", summary="Add night log comment")
async def route_post_night_logs_add_comment(
    data: Annotated[NightLogPostComment, Body(description="The comment to add")],
):
    """Adds a comment to a night log."""

    await add_night_log_comment(
        data.mjd,
        data.comment,
        category=data.category,
        comment_pk=data.pk,
    )


@router.get(
    "/night-logs/comments/delete/{pk}",
    summary="Delete night log comment",
)
async def route_get_night_logs_delete_comment(
    pk: Annotated[int, Path(description="The primary key of the comment")],
):
    """Deletes a comment from a night log."""

    await delete_night_log_comment(pk)


@router.get("/night-logs/{mjd}", summary="Night log data for an MJD")
async def route_get_night_logs_mjd(
    mjd: Annotated[
        int,
        Path(
            description="The MJD for which to retrieve night log data. "
            "Use 0 for tonight's log."
        ),
    ],
):
    """Returns the night log data for an MJD."""

    mjd = mjd if mjd > 0 else get_sjd("LCO")
    data = await get_night_log_data(mjd)

    comments = {
        category: [NightLogComment(**comment) for comment in comments]
        for category, comments in data.pop("comments", {}).items()
    }

    exposure_table_ascii = await get_exposure_table_ascii(mjd)

    return NightLogData(
        **data,
        comments=comments,
        exposure_table=exposure_table_ascii,
    )


@router.get("/night-logs/{mjd}/email", summary="Email night log")
async def route_get_night_logs_mjd_email(
    mjd: Annotated[
        int,
        Path(description="The MJD for which to retrieve night log."),
    ],
    only_if_not_sent: Annotated[
        bool,
        Query(description="Only send the email if it has not been already been sent."),
    ] = False,
):
    """Emails the night log."""

    mjd = mjd if mjd > 0 else get_sjd("LCO")

    try:
        await email_night_log(mjd, only_if_not_sent=only_if_not_sent)
    except Exception as err:
        if "has already been sent" in str(err):
            return False
        raise

    return True


@router.get("/night-logs/{mjd}/plaintext", summary="Plain-text night log")
async def route_get_night_logs_mjd_plaintext(
    mjd: Annotated[
        int,
        Path(description="The MJD for which to retrieve night log."),
    ],
):
    """Returns the night log as a plain-text string."""

    mjd = mjd if mjd > 0 else get_sjd("LCO")
    data = await get_plaintext_night_log(mjd)

    return data
