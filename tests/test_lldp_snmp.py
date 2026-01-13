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
"""Tests for LLDP SNMP parsing utilities."""

from nw_check.lldp_snmp import (
    _build_snmpwalk_command,
    _parse_loc_port_table,
    _parse_rem_table,
    _resolve_device_name,
)
from nw_check.models import Device


def test_resolve_device_name_uses_alias_map() -> None:
    alias_map = {"leaf01": "leaf01", "leaf-1": "leaf01"}

    assert _resolve_device_name("leaf-1", alias_map) == "leaf01"


def test_parse_loc_port_table_extracts_ports() -> None:
    lines = ["LLDP-MIB::lldpLocPortId.1.1 = STRING: Eth1/1"]

    ports = _parse_loc_port_table(lines)

    assert ports["1.1"] == "Eth1/1"


def test_parse_rem_table_groups_rows() -> None:
    lines = [
        "LLDP-MIB::lldpRemChassisId.0.10.1 = STRING: chassisA",
        "LLDP-MIB::lldpRemPortId.0.10.1 = STRING: Eth1/1",
        "LLDP-MIB::lldpRemSysName.0.10.1 = STRING: spine01",
    ]

    rows = _parse_rem_table(lines)

    assert rows[0].local_port == "10"
    assert rows[0].remote_chassis == "chassisA"
    assert rows[0].remote_port == "Eth1/1"
    assert rows[0].remote_sys_name == "spine01"


def test_build_snmpwalk_command_snmpv3_auth_priv() -> None:
    device = Device(
        name="leaf01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha:authpass",
        snmp_priv="aes:privpass",
    )

    command = _build_snmpwalk_command("snmpwalk", device, 2, 1, "LLDP-MIB::lldpRemTable")

    assert command == [
        "snmpwalk",
        "-v",
        "3",
        "-t",
        "2",
        "-r",
        "1",
        "-l",
        "authPriv",
        "-u",
        "snmpuser",
        "-a",
        "sha",
        "-A",
        "authpass",
        "-x",
        "aes",
        "-X",
        "privpass",
        "10.0.0.1",
        "LLDP-MIB::lldpRemTable",
    ]
