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
    _classify_snmpwalk_error,
    _parse_loc_port_table,
    _parse_rem_table,
    _redact_snmp_command,
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


def test_parse_rem_table_multipart_port_index() -> None:
    """Test parsing LLDP remote table with multi-part local port indices.

    For modular/stacked switches, the local port number can be multi-part
    (e.g., "1.49" for module 1, port 49). The LLDP index format is:
    timeMark.localPortNum.remoteIndex, where localPortNum can contain dots.
    """
    lines = [
        "LLDP-MIB::lldpRemChassisId.0.1.49.1 = STRING: chassisB",
        "LLDP-MIB::lldpRemPortId.0.1.49.1 = STRING: Eth1/13",
        "LLDP-MIB::lldpRemSysName.0.1.49.1 = STRING: spine02",
        "LLDP-MIB::lldpRemChassisId.0.1.50.1 = STRING: chassisC",
        "LLDP-MIB::lldpRemPortId.0.1.50.1 = STRING: Eth1/14",
        "LLDP-MIB::lldpRemSysName.0.1.50.1 = STRING: spine03",
    ]

    rows = _parse_rem_table(lines)

    # Should have two rows
    assert len(rows) == 2

    # First row: port 1.49
    assert rows[0].local_port == "1.49"
    assert rows[0].remote_chassis == "chassisB"
    assert rows[0].remote_port == "Eth1/13"
    assert rows[0].remote_sys_name == "spine02"

    # Second row: port 1.50
    assert rows[1].local_port == "1.50"
    assert rows[1].remote_chassis == "chassisC"
    assert rows[1].remote_port == "Eth1/14"
    assert rows[1].remote_sys_name == "spine03"


def test_parse_rem_table_very_long_multipart_index() -> None:
    """Test parsing with very long multi-part port indices (e.g., chassis.slot.module.port)."""
    lines = [
        "LLDP-MIB::lldpRemChassisId.0.1.2.3.49.1 = STRING: chassisD",
        "LLDP-MIB::lldpRemPortId.0.1.2.3.49.1 = STRING: Eth1/2/3/49",
        "LLDP-MIB::lldpRemSysName.0.1.2.3.49.1 = STRING: spine04",
    ]

    rows = _parse_rem_table(lines)

    # Should extract "1.2.3.49" as local port (everything between timeMark and remoteIndex)
    assert rows[0].local_port == "1.2.3.49"
    assert rows[0].remote_chassis == "chassisD"
    assert rows[0].remote_port == "Eth1/2/3/49"
    assert rows[0].remote_sys_name == "spine04"


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
        "SHA",  # Now normalized to uppercase
        "-A",
        "authpass",
        "-x",
        "AES",  # Now normalized to uppercase
        "-X",
        "privpass",
        "10.0.0.1",
        "LLDP-MIB::lldpRemTable",
    ]


def test_redact_snmp_command_hides_secrets() -> None:
    command = [
        "snmpwalk",
        "-v",
        "2c",
        "-c",
        "public",
        "-A",
        "authpass",
        "-X",
        "privpass",
        "10.0.0.1",
        "LLDP-MIB::lldpRemTable",
    ]

    redacted = _redact_snmp_command(command)

    assert redacted[redacted.index("-c") + 1] == "******"
    assert redacted[redacted.index("-A") + 1] == "******"
    assert redacted[redacted.index("-X") + 1] == "******"


def test_classify_snmpwalk_error_auth_failure() -> None:
    output = "Authentication failure (incorrect password, community or key)"

    assert _classify_snmpwalk_error(output) == "SNMP_AUTH_FAILED"


def test_classify_snmpwalk_error_mib_missing() -> None:
    output = "No Such Object available on this agent at this OID"

    assert _classify_snmpwalk_error(output) == "SNMP_MIB_MISSING"


def test_classify_snmpwalk_error_target_unreachable() -> None:
    output = "Timeout: No Response from 10.0.0.1"

    assert _classify_snmpwalk_error(output) == "SNMP_TARGET_UNREACHABLE"


def test_collect_lldp_observations_with_progress() -> None:
    """Test progress reporting during LLDP collection."""
    from nw_check.lldp_snmp import collect_lldp_observations

    devices = [
        Device(
            name="device1",
            mgmt_ip="10.0.0.1",
            snmp_version="2c",
            snmp_community="public",
        ),
        Device(
            name="device2",
            mgmt_ip="10.0.0.2",
            snmp_version="2c",
            snmp_community="public",
        ),
    ]

    # Note: This test will fail if snmpwalk is not available or devices are unreachable
    # But it tests that the function accepts the show_progress parameter
    observations, errors = collect_lldp_observations(
        devices=devices,
        timeout=1,
        retries=0,
        show_progress=True,
    )

    # We expect errors since these devices don't exist
    assert isinstance(observations, list)
    assert isinstance(errors, list)


def test_save_and_load_observations(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Test saving and loading observations for dry-run mode."""

    from nw_check.lldp_snmp import load_observations, save_observations
    from nw_check.models import LinkObservation

    observations = [
        LinkObservation(
            local_device="leaf01",
            local_port_raw="Eth1/1",
            local_port_norm="Eth1/1",
            remote_device_id="chassis01",
            remote_device_name="spine01",
            remote_port_raw="Eth1/1",
            remote_port_norm="Eth1/1",
            source="lldp",
            confidence="observed",
            errors=(),
        ),
        LinkObservation(
            local_device="leaf02",
            local_port_raw="Eth1/2",
            local_port_norm="Eth1/2",
            remote_device_id="unknown",
            remote_device_name="unknown",
            remote_port_raw="unknown",
            remote_port_norm="unknown",
            source="lldp",
            confidence="partial",
            errors=("LLDP_PARTIAL_ROW",),
        ),
    ]

    obs_path = tmp_path / "observations.json"
    save_observations(obs_path, observations)

    loaded = load_observations(obs_path)

    assert len(loaded) == 2
    assert loaded[0].local_device == "leaf01"
    assert loaded[0].confidence == "observed"
    assert loaded[1].local_device == "leaf02"
    assert loaded[1].confidence == "partial"
    assert loaded[1].errors == ("LLDP_PARTIAL_ROW",)


def test_normalize_snmpv3_protocol_auth_lowercase() -> None:
    """Test auth protocol normalization with lowercase input."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("sha", "auth") == "SHA"
    assert _normalize_snmpv3_protocol("md5", "auth") == "MD5"
    assert _normalize_snmpv3_protocol("sha256", "auth") == "SHA-256"
    assert _normalize_snmpv3_protocol("sha-256", "auth") == "SHA-256"


def test_normalize_snmpv3_protocol_auth_uppercase() -> None:
    """Test auth protocol normalization with uppercase input."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("SHA", "auth") == "SHA"
    assert _normalize_snmpv3_protocol("MD5", "auth") == "MD5"
    assert _normalize_snmpv3_protocol("SHA-256", "auth") == "SHA-256"


def test_normalize_snmpv3_protocol_auth_mixed_case() -> None:
    """Test auth protocol normalization with mixed case input."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("Sha", "auth") == "SHA"
    assert _normalize_snmpv3_protocol("Md5", "auth") == "MD5"
    assert _normalize_snmpv3_protocol("SHA-384", "auth") == "SHA-384"


def test_normalize_snmpv3_protocol_auth_unsupported() -> None:
    """Test auth protocol normalization returns None for unsupported protocols."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("sha224", "auth") == "SHA-224"  # sha224 is supported
    assert _normalize_snmpv3_protocol("SHA1", "auth") == "SHA"  # SHA1 is mapped to SHA
    assert _normalize_snmpv3_protocol("invalid", "auth") is None
    assert _normalize_snmpv3_protocol("sha1024", "auth") is None  # Unsupported SHA variant


def test_normalize_snmpv3_protocol_priv_lowercase() -> None:
    """Test priv protocol normalization with lowercase input."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("aes", "priv") == "AES"
    assert _normalize_snmpv3_protocol("des", "priv") == "DES"
    assert _normalize_snmpv3_protocol("aes128", "priv") == "AES"
    assert _normalize_snmpv3_protocol("aes-128", "priv") == "AES"
    assert _normalize_snmpv3_protocol("aes-192", "priv") == "AES-192"
    assert _normalize_snmpv3_protocol("aes-256", "priv") == "AES-256"


def test_normalize_snmpv3_protocol_priv_uppercase() -> None:
    """Test priv protocol normalization with uppercase input."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("AES", "priv") == "AES"
    assert _normalize_snmpv3_protocol("DES", "priv") == "DES"
    assert _normalize_snmpv3_protocol("AES-256", "priv") == "AES-256"


def test_normalize_snmpv3_protocol_priv_unsupported() -> None:
    """Test priv protocol normalization returns None for unsupported protocols."""
    from nw_check.lldp_snmp import _normalize_snmpv3_protocol

    assert _normalize_snmpv3_protocol("3des", "priv") is None
    assert _normalize_snmpv3_protocol("invalid", "priv") is None


def test_validate_snmp_credentials_v3_valid_protocols() -> None:
    """Test SNMPv3 credential validation accepts valid protocols."""
    from nw_check.lldp_snmp import _validate_snmp_credentials

    device = Device(
        name="test01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha:authpass",
        snmp_priv="aes:privpass",
    )
    assert _validate_snmp_credentials(device) is True


def test_validate_snmp_credentials_v3_case_insensitive() -> None:
    """Test SNMPv3 credential validation is case insensitive."""
    from nw_check.lldp_snmp import _validate_snmp_credentials

    device = Device(
        name="test01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="SHA:authpass",
        snmp_priv="AES:privpass",
    )
    assert _validate_snmp_credentials(device) is True


def test_validate_snmp_credentials_v3_protocol_variants() -> None:
    """Test SNMPv3 credential validation accepts protocol variants."""
    from nw_check.lldp_snmp import _validate_snmp_credentials

    # Test SHA-256 variant
    device = Device(
        name="test01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha256:authpass",
        snmp_priv="aes128:privpass",
    )
    assert _validate_snmp_credentials(device) is True

    # Test AES-256 variant
    device2 = Device(
        name="test02",
        mgmt_ip="10.0.0.2",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha-512:authpass",
        snmp_priv="aes-256:privpass",
    )
    assert _validate_snmp_credentials(device2) is True


def test_validate_snmp_credentials_v3_invalid_auth_protocol() -> None:
    """Test SNMPv3 credential validation rejects invalid auth protocols."""
    from nw_check.lldp_snmp import _validate_snmp_credentials

    device = Device(
        name="test01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="invalid:authpass",
        snmp_priv="aes:privpass",
    )
    assert _validate_snmp_credentials(device) is False


def test_validate_snmp_credentials_v3_invalid_priv_protocol() -> None:
    """Test SNMPv3 credential validation rejects invalid priv protocols."""
    from nw_check.lldp_snmp import _validate_snmp_credentials

    device = Device(
        name="test01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha:authpass",
        snmp_priv="3des:privpass",
    )
    assert _validate_snmp_credentials(device) is False


def test_build_snmpwalk_command_normalizes_protocols() -> None:
    """Test that snmpwalk command building normalizes protocol names."""
    device = Device(
        name="leaf01",
        mgmt_ip="10.0.0.1",
        snmp_version="3",
        snmp_user="snmpuser",
        snmp_auth="sha256:authpass",  # lowercase variant
        snmp_priv="aes128:privpass",  # variant without hyphen
    )

    command = _build_snmpwalk_command("snmpwalk", device, 2, 1, "LLDP-MIB::lldpRemTable")

    # Check that protocols are normalized
    assert "-a" in command
    auth_idx = command.index("-a")
    assert command[auth_idx + 1] == "SHA-256"  # Should be normalized

    assert "-x" in command
    priv_idx = command.index("-x")
    assert command[priv_idx + 1] == "AES"  # Should be normalized (aes128 -> AES)
