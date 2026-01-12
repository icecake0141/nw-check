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
"""Tests for deduplication logic."""

from nw_check.link_infer import deduplicate_links
from nw_check.models import LinkObservation


def test_deduplicate_links_merges_bidirectional() -> None:
    observations = [
        LinkObservation(
            local_device="leaf01",
            local_port_raw="Eth1/1",
            local_port_norm="Eth1/1",
            remote_device_id="chassis1",
            remote_device_name="spine01",
            remote_port_raw="Eth1/1",
            remote_port_norm="Eth1/1",
            source="lldp",
            confidence="observed",
            errors=(),
        ),
        LinkObservation(
            local_device="spine01",
            local_port_raw="Eth1/1",
            local_port_norm="Eth1/1",
            remote_device_id="chassis2",
            remote_device_name="leaf01",
            remote_port_raw="Eth1/1",
            remote_port_norm="Eth1/1",
            source="lldp",
            confidence="observed",
            errors=(),
        ),
    ]

    deduped = deduplicate_links(observations)

    assert len(deduped) == 1
    link = deduped[0]
    assert link.confidence == "observed"
    assert link.device_a == "leaf01"
    assert link.device_b == "spine01"


def test_deduplicate_links_handles_partial() -> None:
    observations = [
        LinkObservation(
            local_device="leaf02",
            local_port_raw="Eth1/1",
            local_port_norm="Eth1/1",
            remote_device_id="chassis3",
            remote_device_name="unknown",
            remote_port_raw="unknown",
            remote_port_norm="unknown",
            source="lldp",
            confidence="partial",
            errors=("LLDP_PARTIAL_ROW",),
        )
    ]

    deduped = deduplicate_links(observations)

    assert deduped[0].confidence == "partial"
