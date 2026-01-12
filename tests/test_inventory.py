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
"""Tests for inventory parsing."""

from pathlib import Path

import pytest

from nw_check.inventory import build_device_alias_map, load_device_inventory, load_link_intents


def test_load_device_inventory_parses_aliases(tmp_path: Path) -> None:
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "name,mgmt_ip,snmp_version,snmp_community,aliases\n"
        'leaf01,10.0.0.1,2c,public,"leaf-1,leaf-one"\n',
        encoding="utf-8",
    )

    devices = load_device_inventory(csv_path)

    assert devices[0].aliases == ("leaf-1", "leaf-one")

    alias_map = build_device_alias_map(devices)
    assert alias_map["leaf01"] == "leaf01"
    assert alias_map["leaf-1"] == "leaf01"


def test_load_device_inventory_requires_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text("name,mgmt_ip\nleaf01,10.0.0.1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        load_device_inventory(csv_path)


def test_load_link_intents_requires_fields(tmp_path: Path) -> None:
    csv_path = tmp_path / "tobe.csv"
    csv_path.write_text(
        "device_a,device_b,port_b\nleaf01,spine01,Eth1/1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required columns"):
        load_link_intents(csv_path)


def test_load_link_intents_requires_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "tobe.csv"
    csv_path.write_text(
        "device_a,port_a,device_b,port_b\nleaf01,,spine01,Eth1/1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="empty required fields"):
        load_link_intents(csv_path)
