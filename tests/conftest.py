#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-27
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from fastapi.testclient import TestClient

from lvmapi.app import app


__all__ = ["test_client"]


test_client = TestClient(app, backend="asyncio")
