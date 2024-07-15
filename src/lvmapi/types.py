#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2023-11-11
# @Filename: types.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

from typing import Literal


Spectrographs = Literal["sp1", "sp2", "sp3"]
SpecStatus = Literal["idle", "exposing", "reading", "error", "unknown"]
Cameras = Literal["r", "z", "b"]
CamSpec = Literal["r1", "z1", "b1", "r2", "z2", "b2", "r3", "z3", "b3"]
Sensors = Literal["ccd", "ln2"]

Telescopes = Literal["sci", "spec", "skye", "skyw"]
Frames = Literal["radec", "altaz"]
Coordinates = Literal["ra", "dec", "alt", "az"]
