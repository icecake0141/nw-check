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

import json
from pathlib import Path

from nw_check.models import AsIsLink, LinkDiff, LinkIntent
from nw_check.output import (
    write_asis_links_json,
    write_diff_links_json,
    write_lldp_port_info_markdown,
    write_summary,
    write_summary_json,
)


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


def test_write_asis_links_json(tmp_path: Path) -> None:
    """Test JSON output for As-Is links."""
    links = [
        AsIsLink(
            device_a="leaf01",
            port_a="Eth1/1",
            device_b="spine01",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        ),
        AsIsLink(
            device_a="leaf02",
            port_a="Eth1/2",
            device_b="unknown",
            port_b="unknown",
            confidence="partial",
            evidence=("lldp:missing_remote",),
        ),
    ]

    json_path = tmp_path / "asis_links.json"
    write_asis_links_json(json_path, links)

    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert len(data) == 2
    assert data[0]["local_device"] == "leaf01"
    assert data[0]["local_port"] == "Eth1/1"
    assert data[0]["remote_device"] == "spine01"
    assert data[0]["remote_port"] == "Eth1/1"
    assert data[0]["confidence"] == "observed"
    assert data[0]["evidence"] == ["lldp"]

    assert data[1]["local_device"] == "leaf02"
    assert data[1]["confidence"] == "partial"


def test_write_diff_links_json(tmp_path: Path) -> None:
    """Test JSON output for diff links."""
    diffs = [
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf01",
                port_a_raw="Eth1/1",
                port_a_norm="Eth1/1",
                device_b="spine01",
                port_b_raw="Eth1/1",
                port_b_norm="Eth1/1",
            ),
            asis_link=AsIsLink(
                device_a="leaf01",
                port_a="Eth1/1",
                device_b="spine01",
                port_b="Eth1/1",
                confidence="observed",
                evidence=("lldp",),
            ),
            status="EXACT_MATCH",
            reason="normalized ports matched",
        ),
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf01",
                port_a_raw="Eth1/2",
                port_a_norm="Eth1/2",
                device_b="spine01",
                port_b_raw="Eth1/2",
                port_b_norm="Eth1/2",
            ),
            asis_link=None,
            status="MISSING_ASIS",
            reason="no lldp observation",
        ),
    ]

    json_path = tmp_path / "diff_links.json"
    write_diff_links_json(json_path, diffs)

    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert len(data) == 2
    assert data[0]["device_a"] == "leaf01"
    assert data[0]["port_a"] == "Eth1/1"
    assert data[0]["status"] == "EXACT_MATCH"
    assert data[1]["status"] == "MISSING_ASIS"


def test_write_summary_json(tmp_path: Path) -> None:
    """Test JSON output for summary."""
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

    json_path = tmp_path / "summary.json"
    write_summary_json(json_path, [diff], ["leaf01", "leaf02"], asis_links)

    content = json_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert data["lldp_failed_devices"] == ["leaf01", "leaf02"]
    assert data["missing_ports"] == 1
    assert data["mismatch_links"] == 1


def test_write_lldp_port_info_markdown(tmp_path: Path) -> None:
    """Test Markdown output for LLDP and port information."""
    asis_links = [
        AsIsLink(
            device_a="leaf01",
            port_a="Eth1/1",
            device_b="spine01",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        ),
        AsIsLink(
            device_a="leaf02",
            port_a="Eth1/2",
            device_b="unknown",
            port_b="unknown",
            confidence="partial",
            evidence=("lldp:missing_remote",),
        ),
    ]

    diffs = [
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf01",
                port_a_raw="Eth1/1",
                port_a_norm="Eth1/1",
                device_b="spine01",
                port_b_raw="Eth1/1",
                port_b_norm="Eth1/1",
            ),
            asis_link=asis_links[0],
            status="EXACT_MATCH",
            reason="normalized ports matched",
        ),
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf01",
                port_a_raw="Eth1/2",
                port_a_norm="Eth1/2",
                device_b="spine01",
                port_b_raw="Eth1/2",
                port_b_norm="Eth1/2",
            ),
            asis_link=None,
            status="MISSING_ASIS",
            reason="no lldp observation",
        ),
    ]

    md_path = tmp_path / "lldp_port_info.md"
    write_lldp_port_info_markdown(md_path, asis_links, diffs, ["leaf03"])

    content = md_path.read_text(encoding="utf-8")

    # Check header
    assert "# LLDP and Port Information" in content

    # Check summary section
    assert "## Summary" in content
    assert "**Total Links Discovered**: 2" in content
    assert "**Exact Matches**: 1" in content
    assert "**Mismatches**: 1" in content
    assert "**Links with Missing Port Info**: 1" in content
    assert "**Devices with LLDP Collection Failures**: 1" in content
    assert "Failed devices: leaf03" in content

    # Check As-Is Links table
    assert "## As-Is Links (Discovered via LLDP)" in content
    assert (
        "| Local Device | Local Port | Remote Device | Remote Port | Confidence | Evidence |"
    ) in content
    assert "| leaf01 | Eth1/1 | spine01 | Eth1/1 | observed | lldp |" in content
    assert ("| leaf02 | Eth1/2 | unknown | unknown | partial | lldp:missing_remote |") in content

    # Check To-Be vs As-Is Comparison table
    assert "## To-Be vs As-Is Comparison" in content
    assert "| Device A | Port A | Device B | Port B | Status | Reason |" in content
    assert (
        "| leaf01 | Eth1/1 | spine01 | Eth1/1 | EXACT_MATCH | normalized ports matched |"
    ) in content
    assert (
        "| leaf01 | Eth1/2 | spine01 | Eth1/2 | MISSING_ASIS | no lldp observation |"
    ) in content
