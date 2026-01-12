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
"""Tests for output rendering."""

from pathlib import Path

from nw_check.models import AsIsLink, LinkDiff, LinkIntent
from nw_check.output import write_summary


def test_write_summary_counts_missing_ports(tmp_path: Path) -> None:
    diff = LinkDiff(
        tobe_link=LinkIntent(
            device_a="leaf01",
            port_a_raw="Eth1/1",
            port_a_norm="Eth1/1",
            device_b="spine01",
            port_b_raw="Eth1/1",
            port_b_norm="Eth1/1",
        ),
        asis_link=None,
        status="MISSING_ASIS",
        reason="no lldp observation",
    )
    asis_links = [
        AsIsLink(
            device_a="leaf01",
            port_a="unknown",
            device_b="spine01",
            port_b="Eth1/1",
            confidence="partial",
            evidence=("lldp",),
        )
    ]

    summary_path = tmp_path / "summary.txt"

    write_summary(summary_path, [diff], ["leaf01"], asis_links)

    content = summary_path.read_text(encoding="utf-8")
    assert "missing_ports: 1" in content
    assert "lldp_failed_devices: leaf01" in content
    assert "mismatch_links: 1" in content
