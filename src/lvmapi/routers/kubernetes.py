#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-07-25
# @Filename: kubernetes.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

from lvmapi.tasks import restart_kubernetes_deployment_task


if TYPE_CHECKING:
    from lvmapi.tools.kubernetes import Kubernetes


router = APIRouter(prefix="/kubernetes", tags=["kubernetes"])


@router.get("/deployments")
@router.get("/deployments/list")
async def list_deployments(request: Request) -> list[str]:
    """Lists the deployments in all namespaces."""

    kube: Kubernetes = request.app.state.kubernetes

    return kube.list_deployments()


@router.get("/deployments/{deployment}/restart")
async def restart_deployment(deployment: str) -> str:
    """Restarts a deployment. Scheduled as a task (returns task ID)."""

    task = await restart_kubernetes_deployment_task.kiq(deployment)
    return task.task_id
