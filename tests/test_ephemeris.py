#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2024-12-27
# @Filename: test_ephemeris.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from sdsstools.time import get_sjd

from lvmapi.routers.ephemeris import EphemerisSummaryOut

from .conftest import test_client


async def test_ephemeris_summary():
    response = test_client.get("/ephemeris/summary")
    assert response.status_code == 200
    assert EphemerisSummaryOut.model_validate(response.json())


async def test_ephemeris_sjd():
    response = test_client.get("/ephemeris/sjd")
    assert response.status_code == 200
    assert response.json() == get_sjd("LCO")
