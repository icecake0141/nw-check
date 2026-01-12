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
"""Inventory and To-Be CSV parsing."""

from __future__ import annotations

import csv
from pathlib import Path

from nw_check.models import Device, LinkIntent
from nw_check.normalize import normalize_interface_name


def load_device_inventory(path: str | Path) -> list[Device]:
    """Load device inventory CSV."""

    devices: list[Device] = []
    with Path(path).open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            device = Device(
                name=(row.get("name") or "").strip(),
                mgmt_ip=(row.get("mgmt_ip") or "").strip(),
                snmp_version=(row.get("snmp_version") or "").strip(),
                snmp_community=(row.get("snmp_community") or "").strip() or None,
                snmp_user=(row.get("snmp_user") or "").strip() or None,
                snmp_auth=(row.get("snmp_auth") or "").strip() or None,
                snmp_priv=(row.get("snmp_priv") or "").strip() or None,
            )
            devices.append(device)
    return devices


def load_link_intents(path: str | Path) -> list[LinkIntent]:
    """Load To-Be wiring CSV."""

    intents: list[LinkIntent] = []
    with Path(path).open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            device_a = (row.get("device_a") or "").strip()
            port_a_raw = (row.get("port_a") or "").strip()
            device_b = (row.get("device_b") or "").strip()
            port_b_raw = (row.get("port_b") or "").strip()
            intents.append(
                LinkIntent(
                    device_a=device_a,
                    port_a_raw=port_a_raw,
                    port_a_norm=normalize_interface_name(port_a_raw),
                    device_b=device_b,
                    port_b_raw=port_b_raw,
                    port_b_norm=normalize_interface_name(port_b_raw),
                )
            )
    return intents
