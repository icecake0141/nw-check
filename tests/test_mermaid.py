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
"""Tests for Mermaid diagram generation."""

from pathlib import Path

from nw_check.mermaid import generate_mermaid_diagram, write_mermaid_diagram
from nw_check.models import AsIsLink, LinkDiff, LinkIntent


def test_generate_mermaid_diagram_basic() -> None:
    """Test basic Mermaid diagram generation."""
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
            port_a="Eth1/1",
            device_b="spine01",
            port_b="Eth1/2",
            confidence="observed",
            evidence=("lldp",),
        ),
    ]

    diagram = generate_mermaid_diagram(links)

    assert "graph LR" in diagram
    assert "leaf01" in diagram
    assert "leaf02" in diagram
    assert "spine01" in diagram
    assert "Eth1/1" in diagram


def test_generate_mermaid_diagram_with_diffs() -> None:
    """Test Mermaid diagram generation with diff status coloring."""
    links = [
        AsIsLink(
            device_a="leaf01",
            port_a="Eth1/1",
            device_b="spine01",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
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
            asis_link=links[0],
            status="EXACT_MATCH",
            reason="ports matched",
        ),
    ]

    diagram = generate_mermaid_diagram(links, diffs)

    assert "graph LR" in diagram
    assert "Styling" in diagram
    assert "fill:#ccffcc" in diagram  # Green for exact match


def test_generate_mermaid_diagram_filters_unknown() -> None:
    """Test that unknown devices are filtered out."""
    links = [
        AsIsLink(
            device_a="leaf01",
            port_a="Eth1/1",
            device_b="unknown",
            port_b="unknown",
            confidence="partial",
            evidence=("lldp",),
        ),
    ]

    diagram = generate_mermaid_diagram(links)

    assert "unknown" not in diagram


def test_generate_mermaid_diagram_respects_max_nodes() -> None:
    """Test that max_nodes limit is respected."""
    # Create 60 devices (more than default max of 50)
    links = [
        AsIsLink(
            device_a=f"device{i:02d}",
            port_a="Eth1/1",
            device_b=f"device{i+1:02d}",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        )
        for i in range(60)
    ]

    diagram = generate_mermaid_diagram(links, max_nodes=10)

    # Count unique devices in diagram (should be at most 10)
    device_count = sum(1 for i in range(60) if f"device{i:02d}" in diagram)
    assert device_count <= 10


def test_write_mermaid_diagram(tmp_path: Path) -> None:
    """Test writing Mermaid diagram to file."""
    links = [
        AsIsLink(
            device_a="leaf01",
            port_a="Eth1/1",
            device_b="spine01",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        ),
    ]

    mmd_path = tmp_path / "topology.mmd"
    write_mermaid_diagram(mmd_path, links)

    assert mmd_path.exists()
    content = mmd_path.read_text(encoding="utf-8")
    assert "graph LR" in content
    assert "leaf01" in content
