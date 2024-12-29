#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: actors.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from lvmapi import config
from lvmapi.tasks import restart_kubernetes_deployment_task
from lvmapi.tools.logs import get_actor_versions
from lvmapi.tools.rabbitmq import ping_actors


class HealthResponse(BaseModel):
    """Health response for an actor."""

    actor: str
    deployment_name: str
    is_deployed: bool
    ping: bool


router = APIRouter(prefix="/actors", tags=["actors"])


@router.get("/", summary="List of actors")
async def get_actors_route() -> list[str]:
    """Returns a list of actors."""

    return config["actors"]["list"]


@router.get("/health", summary="Actor health")
async def get_actor_health(request: Request) -> list[HealthResponse]:
    """Returns the health of all actors."""

    actors = config["actors"]["list"]
    health: list[HealthResponse] = []

    deployments = request.app.state.kubernetes.list_deployments()
    ping_response = await ping_actors(actors=actors)

    for actor in actors:
        deployment_name = config["actors.actor_to_deployment"][actor]
        ping = ping_response.get(actor, False)
        is_deployed = deployment_name in deployments
        health.append(
            HealthResponse(
                actor=actor,
                deployment_name=deployment_name,
                is_deployed=is_deployed,
                ping=ping,
            )
        )

    return health


@router.get("/actor-to-deployment", summary="Get actor to deployment mapping")
async def get_actor_to_deployment_route() -> dict[str, str]:
    """Returns the actor to deployment mapping."""

    return config["actors.actor_to_deployment"]


@router.get("/deployment-to-actors", summary="Get deployment to actors mapping")
async def get_deployment_to_actors_route() -> dict[str, list[str]]:
    """Returns the deployment to actors mapping."""

    actor_to_deployment = config["actors.actor_to_deployment"]

    deployment_to_actors = {}
    for actor, deployment in actor_to_deployment.items():
        if deployment not in deployment_to_actors:
            deployment_to_actors[deployment] = []
        deployment_to_actors[deployment].append(actor)

    return deployment_to_actors


@router.get("/ping", summary="Actor ping")
async def get_ping_route(actors: list[str] | None = None) -> dict[str, bool]:
    """Pings a list of actors."""

    return await ping_actors(actors=actors)


@router.get("/restart/{actor}", summary="Restart an actor")
async def get_restart_actor_route(actor: str) -> str:
    """Restarts an actor. Scheduled as a task and returns the task ID"""

    deployment = config["actors.actor_to_deployment"][actor]
    if deployment is None:
        raise ValueError(f"Actor {actor} does not have a deployment.")

    task = await restart_kubernetes_deployment_task.kiq(deployment)
    return task.task_id


@router.get("/stop/{actor}", summary="Stop an actor")
async def get_stop_actor_route(actor: str) -> bool:
    """Stops an actor."""

    from lvmapi.app import app

    deployment = config["actors.actor_to_deployment"][actor]
    if deployment is None:
        raise ValueError(f"Actor {actor} does not have a deployment.")

    app.state.kubernetes.delete_deployment(deployment)

    return True


@router.get("/versions", summary="Get actor versions")
async def get_actor_versions_route(
    actor: Annotated[
        str | None,
        Query(description="Optionally, actor for which to return the version"),
    ] = None,
) -> dict[str, str | None]:
    """Returns the version of an actor."""

    return await get_actor_versions(actor=actor)
