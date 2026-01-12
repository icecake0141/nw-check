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
"""Data models for nw-check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

UNKNOWN_VALUE = "unknown"


@dataclass(frozen=True)
class Device:
    """Device inventory record."""

    name: str
    mgmt_ip: str
    snmp_version: str
    snmp_community: str | None = None
    snmp_user: str | None = None
    snmp_auth: str | None = None
    snmp_priv: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinkObservation:
    """Directional LLDP observation collected from a device."""

    local_device: str
    local_port_raw: str
    local_port_norm: str
    remote_device_id: str
    remote_device_name: str
    remote_port_raw: str
    remote_port_norm: str
    source: str
    confidence: str
    errors: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class AsIsLink:
    """Deduplicated LLDP link."""

    device_a: str
    port_a: str
    device_b: str
    port_b: str
    confidence: str
    evidence: Sequence[str]


@dataclass(frozen=True)
class LinkIntent:
    """Desired wiring intent (To-Be)."""

    device_a: str
    port_a_raw: str
    port_a_norm: str
    device_b: str
    port_b_raw: str
    port_b_norm: str


@dataclass(frozen=True)
class LinkDiff:
    """Comparison result between To-Be and As-Is links."""

    tobe_link: LinkIntent
    asis_link: AsIsLink | None
    status: str
    reason: str
