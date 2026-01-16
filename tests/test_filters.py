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
"""Tests for filtering utilities."""

from nw_check.filters import filter_asis_links, filter_diffs
from nw_check.models import AsIsLink, LinkDiff, LinkIntent


def test_filter_asis_links_by_device_list() -> None:
    """Test filtering As-Is links by device name list."""
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
        AsIsLink(
            device_a="leaf03",
            port_a="Eth1/1",
            device_b="spine02",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        ),
    ]

    filtered = filter_asis_links(links, device_filter=["leaf01", "spine01"])

    assert len(filtered) == 2
    assert all(
        "leaf01" in (link.device_a, link.device_b) or "spine01" in (link.device_a, link.device_b)
        for link in filtered
    )


def test_filter_asis_links_by_regex() -> None:
    """Test filtering As-Is links by regex pattern."""
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
        AsIsLink(
            device_a="core01",
            port_a="Eth1/1",
            device_b="core02",
            port_b="Eth1/1",
            confidence="observed",
            evidence=("lldp",),
        ),
    ]

    # Filter for devices starting with "leaf"
    filtered = filter_asis_links(links, device_regex=r"^leaf")

    assert len(filtered) == 2
    assert all("leaf" in link.device_a or "leaf" in link.device_b for link in filtered)


def test_filter_diffs_by_status() -> None:
    """Test filtering diffs by status."""
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
            asis_link=None,
            status="EXACT_MATCH",
            reason="matched",
        ),
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf02",
                port_a_raw="Eth1/1",
                port_a_norm="Eth1/1",
                device_b="spine01",
                port_b_raw="Eth1/2",
                port_b_norm="Eth1/2",
            ),
            asis_link=None,
            status="PORT_MISMATCH",
            reason="port differs",
        ),
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf03",
                port_a_raw="Eth1/1",
                port_a_norm="Eth1/1",
                device_b="spine01",
                port_b_raw="Eth1/3",
                port_b_norm="Eth1/3",
            ),
            asis_link=None,
            status="MISSING_ASIS",
            reason="no observation",
        ),
    ]

    filtered = filter_diffs(diffs, status_filter=["PORT_MISMATCH", "MISSING_ASIS"])

    assert len(filtered) == 2
    assert all(diff.status in ("PORT_MISMATCH", "MISSING_ASIS") for diff in filtered)


def test_filter_diffs_by_device_and_status() -> None:
    """Test filtering diffs by both device and status."""
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
            asis_link=None,
            status="EXACT_MATCH",
            reason="matched",
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
            status="PORT_MISMATCH",
            reason="port differs",
        ),
        LinkDiff(
            tobe_link=LinkIntent(
                device_a="leaf02",
                port_a_raw="Eth1/1",
                port_a_norm="Eth1/1",
                device_b="spine02",
                port_b_raw="Eth1/1",
                port_b_norm="Eth1/1",
            ),
            asis_link=None,
            status="PORT_MISMATCH",
            reason="port differs",
        ),
    ]

    # Filter for leaf01 with PORT_MISMATCH status
    filtered = filter_diffs(
        diffs, device_filter=["leaf01"], device_regex=None, status_filter=["PORT_MISMATCH"]
    )

    assert len(filtered) == 1
    assert filtered[0].tobe_link.device_a == "leaf01"
    assert filtered[0].status == "PORT_MISMATCH"


def test_filter_returns_all_when_no_filters() -> None:
    """Test that filtering returns all items when no filters specified."""
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

    filtered = filter_asis_links(links)
    assert len(filtered) == len(links)
