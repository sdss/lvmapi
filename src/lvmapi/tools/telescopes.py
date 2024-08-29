#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-08-29
# @Filename: telescopes.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Any

from lvmapi.tools.rabbitmq import CluClient
from lvmapi.types import Telescopes


async def get_telescope_status(telescope: Telescopes) -> dict[str, Any]:
    """Gets the status of a telescope."""

    async with CluClient() as client:
        status_cmd = await client.send_command(f"lvm.{telescope}.pwi", "status")

    if status_cmd.status.did_fail:
        raise ValueError(f"Failed to get status for telescope {telescope!r}.")

    return {
        "ra": status_cmd.replies.get("ra_j2000_hours") * 15.0,
        "dec": status_cmd.replies.get("dec_apparent_degs"),
        "alt": status_cmd.replies.get("altitude_degs"),
        "az": status_cmd.replies.get("azimuth_degs"),
        "is_tracking": status_cmd.replies.get("is_tracking"),
        "is_connected": status_cmd.replies.get("is_connected"),
        "is_slewing": status_cmd.replies.get("is_slewing"),
        "is_enabled": status_cmd.replies.get("is_enabled"),
    }
