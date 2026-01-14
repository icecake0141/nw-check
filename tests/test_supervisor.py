# Copyright 2025 nw-check contributors
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This file was created or modified with the assistance of an AI (Large Language Model).
# Review required for correctness, security, and licensing.
"""Tests for the nw-check supervisor."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from nw_check.supervisor import ProcessSupervisor, build_nw_check_command


@pytest.mark.skipif(os.name != "posix", reason="pause/resume relies on POSIX signals")
def test_pause_resume_terminate() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(5)"]
    supervisor = ProcessSupervisor(command, terminate_timeout=1.0)
    supervisor.start()

    try:
        assert supervisor.status()["status"] == "running"
        ok, message = supervisor.pause()
        assert ok, message
        assert supervisor.status()["status"] == "paused"
        ok, message = supervisor.resume()
        assert ok, message
        assert supervisor.status()["status"] == "running"
    finally:
        ok, message = supervisor.terminate()
        assert ok, message
        assert supervisor.status()["status"] == "exited"


def test_build_nw_check_command() -> None:
    args = SimpleNamespace(
        devices="devices.csv",
        tobe="tobe.csv",
        out_dir="out",
        snmp_timeout=3,
        snmp_retries=2,
        snmp_verbose=True,
        log_level="DEBUG",
    )
    command = build_nw_check_command(args)
    assert command[:3] == [sys.executable, "-m", "nw_check.cli"]
    assert "--snmp-verbose" in command
