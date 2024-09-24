#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-06
# @Filename: log.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import io
from datetime import datetime

from typing import Annotated, Any

import polars
from fastapi import APIRouter, Body, Path, Query
from pydantic import BaseModel, Field

from sdsstools import get_sjd

from lvmapi.tasks import get_exposure_data_task
from lvmapi.tools.logs import (
    add_night_log_comment,
    create_night_log_entry,
    delete_night_log_comment,
    get_exposure_data,
    get_exposures,
    get_night_log_data,
    get_night_log_mjds,
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

    await add_night_log_comment(data.mjd, data.comment, category=data.category)


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

    exposure_data = await route_get_exposures_data(mjd, as_task=False)
    assert isinstance(exposure_data, dict)

    exposure_records: list[dict[str, Any]] = []
    for exp in exposure_data.values():
        exp_dict = dict(exp)

        # No need for the mjd column.
        exp_dict.pop("mjd")

        # Convert the lamps to a string
        lamps = exp_dict.pop("lamps")
        lamps_on = ",".join([lamp for lamp, on in lamps.items() if on])
        exp_dict["lamps"] = lamps_on

        exposure_records.append(exp_dict)

    if len(exposure_records) == 0:
        exposure_table_ascii = None
    else:
        exposure_df = polars.DataFrame(exposure_records)

        # Rename some columns to make the table narrower.
        # Use only second precision in obstime.
        exposure_df = exposure_df.rename(
            {
                "exposure_no": "exposure",
                "image_type": "type",
                "exposure_time": "exp_time",
                "n_standards": "n_std",
                "n_cameras": "n_cam",
            }
        ).with_columns(
            obstime=polars.col.obstime.str.replace("T", " ").str.replace(r"\.\d+", "")
        )

        n_tiles = exposure_df.filter(
            polars.col.type == "object",
            polars.col.object.str.starts_with("tile_id="),
        ).height

        exposure_io = io.StringIO()
        with polars.Config(
            tbl_formatting="ASCII_FULL_CONDENSED",
            tbl_hide_column_data_types=True,
            tbl_hide_dataframe_shape=True,
            tbl_cols=-1,
            tbl_rows=-1,
            tbl_width_chars=1000,
        ):
            print(f"# science_tiles: {n_tiles}\n", file=exposure_io)
            print(exposure_df, file=exposure_io)

        exposure_io.seek(0)
        exposure_table_ascii = exposure_io.read()

    return NightLogData(
        **data,
        comments=comments,
        exposure_table=exposure_table_ascii,
    )
