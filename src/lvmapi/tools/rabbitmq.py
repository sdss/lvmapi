#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-12
# @Filename: rabbitmq.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import os

from typing import TYPE_CHECKING, Any, Literal, overload

from clu import AMQPClient
from sdsstools.utils import GatheringTaskGroup

from lvmapi import config


if TYPE_CHECKING:
    from clu import Command


__all__ = ["CluClient", "send_clu_command", "ping_actors"]


class CluClient:
    """AMQP client asynchronous generator.

    Returns an object with an ``AMQPClient`` instance. The normal way to
    use it is to do ::

        async with CluClient() as client:
            await client.send_command(...)

    Alternatively one can do ::

        client = await anext(CluClient())
        await client.send_command(...)

    The asynchronous generator differs from the one in ``AMQPClient`` in that
    it does not close the connection on exit.

    This class is a singleton, which effectively means the AMQP client is reused
    during the life of the worker. The singleton can be cleared by calling
    `.clear`.

    """

    __initialised: bool = False
    __instance: CluClient | None = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(CluClient, cls).__new__(cls)
            cls.__instance.__initialised = False

        return cls.__instance

    def __init__(self):
        if self.__initialised is True:
            return

        host: str = os.environ.get("RABBITMQ_HOST", config["rabbitmq.host"])
        port: int = int(os.environ.get("RABBITMQ_PORT", config["rabbitmq.port"]))

        self.client = AMQPClient(host=host, port=port)
        self.__initialised = True

    async def __aenter__(self):
        if not self.client.is_connected():
            await self.client.start()

        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __anext__(self):
        if not self.client.is_connected():
            await self.client.start()

        return self.client

    @classmethod
    def clear(cls):
        """Clears the current instance."""

        cls.__instance = None
        cls.__initialised = False


@overload
async def send_clu_command(command_string: str) -> list[dict[str, Any]]: ...


@overload
async def send_clu_command(
    command_string: str,
    *,
    raw: Literal[False],
) -> list[dict[str, Any]]: ...


@overload
async def send_clu_command(
    command_string: str,
    *,
    raw: Literal[True],
) -> Command: ...


@overload
async def send_clu_command(
    command_string: str,
    *,
    raw: bool,
) -> list[dict[str, Any]] | Command: ...


async def send_clu_command(
    command_string: str,
    *,
    raw=False,
) -> list[dict[str, Any]] | Command:
    """Sends a command to the actor system and returns a list of replies.

    Parameters
    ----------
    command_string
        The command to send to the actor. Must include the name of the actor.
    raw
        If `True`, returns the command. Otherwise returns a list of replies.

    Returns
    -------
    replies
        A list of replies, each one a dictionary of keyword to value. Empty
        replies (e.g., those only changing the status) are not returned. If
        ``raw=True``, the CLU command is returned after awaiting for it to
        complete or fail.

    Raises
    ------
    RuntimeError
        If the command fails, times out, or is otherwise not successful.

    """

    consumer, *rest = command_string.split(" ")

    async with CluClient() as client:
        cmd = await client.send_command(consumer, " ".join(rest))

    if cmd.status.did_succeed:
        if raw:
            return cmd

        replies: list[dict[str, Any]] = []
        for reply in cmd.replies:
            if len(reply.message) == 0:
                continue
            replies.append(reply.message)
        return replies

    raise RuntimeError(f"Command {command_string!r} failed.")


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
