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
"""Tests for diff logic."""

from nw_check.diff import (
    STATUS_DEVICE_MISMATCH,
    STATUS_EXACT_MATCH,
    STATUS_MISSING_ASIS,
    STATUS_PORT_MISMATCH,
    STATUS_PARTIAL_OBSERVED,
    diff_links,
)
from nw_check.models import AsIsLink, LinkIntent


def test_diff_links_exact_match() -> None:
    intent = LinkIntent(
        device_a="leaf01",
        port_a_raw="Eth1/1",
        port_a_norm="Eth1/1",
        device_b="spine01",
        port_b_raw="Eth1/1",
        port_b_norm="Eth1/1",
    )
    asis = AsIsLink(
        device_a="leaf01",
        port_a="Eth1/1",
        device_b="spine01",
        port_b="Eth1/1",
        confidence="observed",
        evidence=("lldp",),
    )

    result = diff_links([intent], [asis])

    assert result[0].status == STATUS_EXACT_MATCH


def test_diff_links_port_mismatch() -> None:
    intent = LinkIntent(
        device_a="leaf01",
        port_a_raw="Eth1/1",
        port_a_norm="Eth1/1",
        device_b="spine01",
        port_b_raw="Eth1/2",
        port_b_norm="Eth1/2",
    )
    asis = AsIsLink(
        device_a="leaf01",
        port_a="Eth1/1",
        device_b="spine01",
        port_b="Eth1/3",
        confidence="observed",
        evidence=("lldp",),
    )

    result = diff_links([intent], [asis])

    assert result[0].status == STATUS_PORT_MISMATCH


def test_diff_links_device_mismatch() -> None:
    intent = LinkIntent(
        device_a="leaf01",
        port_a_raw="Eth1/1",
        port_a_norm="Eth1/1",
        device_b="spine01",
        port_b_raw="Eth1/2",
        port_b_norm="Eth1/2",
    )
    asis = AsIsLink(
        device_a="leaf02",
        port_a="Eth1/1",
        device_b="spine02",
        port_b="Eth1/2",
        confidence="observed",
        evidence=("lldp",),
    )

    result = diff_links([intent], [asis])

    assert result[0].status == STATUS_DEVICE_MISMATCH


def test_diff_links_missing_asis() -> None:
    intent = LinkIntent(
        device_a="leaf01",
        port_a_raw="Eth1/1",
        port_a_norm="Eth1/1",
        device_b="spine01",
        port_b_raw="Eth1/2",
        port_b_norm="Eth1/2",
    )

    result = diff_links([intent], [])

    assert result[0].status == STATUS_MISSING_ASIS


def test_diff_links_partial_includes_candidate_details() -> None:
    intent = LinkIntent(
        device_a="leaf01",
        port_a_raw="Eth1/1",
        port_a_norm="Eth1/1",
        device_b="spine01",
        port_b_raw="Eth1/1",
        port_b_norm="Eth1/1",
    )
    asis = AsIsLink(
        device_a="leaf01",
        port_a="Eth1/1",
        device_b="chassis-raw",
        port_b="unknown",
        confidence="partial",
        evidence=("lldp",),
    )

    result = diff_links([intent], [asis])

    assert result[0].status == STATUS_PARTIAL_OBSERVED
    assert "chassis-raw" in result[0].reason
