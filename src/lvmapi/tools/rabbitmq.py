#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: rabbitmq.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

from lvmopstools.clu import CluClient, send_clu_command
from sdsstools.utils import GatheringTaskGroup

from lvmapi import config


if TYPE_CHECKING:
    pass


__all__ = ["CluClient", "send_clu_command", "ping_actors"]


async def ping_actors(actors: list[str] | None = None):
    """Pings all actors and returns a list of replies."""

    actors = actors or config["actors"]["list"]
    assert actors is not None

    async with CluClient() as client:
        async with GatheringTaskGroup() as group:
            for actor in actors:
                group.create_task(client.send_command(actor, "ping"))

    results = group.results()

    actor_to_pong: dict[str, bool] = {}
    for idx, result in enumerate(results):
        replies = result.replies

        if "text" in replies[-1].message and replies[-1].message["text"] == "Pong.":
            actor_to_pong[actors[idx]] = True
        else:
            actor_to_pong[actors[idx]] = False

    return actor_to_pong
