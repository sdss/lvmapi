#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: kubernetes.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from lvmapi.tasks import restart_kubernetes_deployment_task


if TYPE_CHECKING:
    from lvmopstools.kubernetes import Kubernetes


class DeploymentInfoResponse(BaseModel):
    """Response for deployment info."""

    api_version: str | None
    kind: str | None
    metadata: dict[str, Any]
    status: dict[str, Any]


router = APIRouter(prefix="/kubernetes", tags=["kubernetes"])


@router.get("/deployments", summary="Lists the deployments")
@router.get("/deployments/list", summary="Lists the deployments")
async def route_get_list_deployments(request: Request) -> list[str]:
    """Lists the deployments in all namespaces."""

    kube: Kubernetes = request.app.state.kubernetes

    return kube.list_deployments()


@router.get("/deployments/{deployment}/restart", summary="Restart deployment")
async def route_get_restart_deployment(deployment: str) -> str:
    """Restarts a deployment. Scheduled as a task (returns task ID)."""

    task = await restart_kubernetes_deployment_task.kiq(deployment)
    return task.task_id


@router.get("/deployments/{deployment}/info", summary="Get deployment info")
async def route_get_deployment_info(request: Request, deployment: str):
    """Returns information about a deployment."""

    kube: Kubernetes = request.app.state.kubernetes

    info = kube.get_deployment_info(deployment)

    return DeploymentInfoResponse(**info)
