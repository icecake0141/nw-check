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
"""LLDP collection via SNMP using the snmpwalk CLI."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from nw_check.models import UNKNOWN_VALUE, Device, LinkObservation
from nw_check.normalize import normalize_interface_name

_LOGGER = logging.getLogger(__name__)

LLDP_REM_TABLE = "LLDP-MIB::lldpRemTable"
LLDP_LOC_PORT_TABLE = "LLDP-MIB::lldpLocPortTable"


@dataclass(frozen=True)
class DeviceCollectionResult:
    """Result of collecting LLDP information from a single device."""

    observations: list[LinkObservation]
    errors: list[str]


def collect_lldp_observations(
    devices: Iterable[Device],
    timeout: int,
    retries: int,
    alias_map: dict[str, str] | None = None,
    snmpwalk_cmd: str = "snmpwalk",
) -> tuple[list[LinkObservation], list[str]]:
    """Collect LLDP neighbor data from devices via SNMP walk."""

    all_observations: list[LinkObservation] = []
    failed_devices: list[str] = []
    for device in devices:
        result = _collect_for_device(device, timeout, retries, alias_map, snmpwalk_cmd)
        all_observations.extend(result.observations)
        if result.errors:
            failed_devices.append(device.name)
    return all_observations, failed_devices


def _collect_for_device(
    device: Device,
    timeout: int,
    retries: int,
    alias_map: dict[str, str] | None,
    snmpwalk_cmd: str,
) -> DeviceCollectionResult:
    """Collect LLDP data for a single device using snmpwalk."""

    errors: list[str] = []
    if not device.snmp_community:
        errors.append("SNMP_AUTH_FAILED")
        return DeviceCollectionResult([], errors)

    if not _command_exists(snmpwalk_cmd):
        errors.append("SNMP_OID_UNSUPPORTED")
        return DeviceCollectionResult([], errors)

    loc_port_output = _run_snmpwalk(snmpwalk_cmd, device, timeout, retries, LLDP_LOC_PORT_TABLE)
    if loc_port_output is None:
        errors.append("SNMP_TIMEOUT")
        return DeviceCollectionResult([], errors)

    rem_output = _run_snmpwalk(snmpwalk_cmd, device, timeout, retries, LLDP_REM_TABLE)
    if rem_output is None:
        errors.append("SNMP_TIMEOUT")
        return DeviceCollectionResult([], errors)

    loc_ports = _parse_loc_port_table(loc_port_output)
    rem_rows = _parse_rem_table(rem_output)
    if not rem_rows:
        errors.append("LLDP_TABLE_EMPTY")
        return DeviceCollectionResult([], errors)

    observations: list[LinkObservation] = []
    for row in rem_rows:
        local_port_raw = loc_ports.get(row.local_port) or UNKNOWN_VALUE
        local_port_norm = normalize_interface_name(local_port_raw)
        remote_port_norm = normalize_interface_name(row.remote_port)
        remote_device_name = _resolve_device_name(row.remote_sys_name, alias_map)
        confidence = "observed"
        error_list: list[str] = []
        if remote_device_name == UNKNOWN_VALUE or row.remote_port == UNKNOWN_VALUE:
            confidence = "partial"
            error_list.append("LLDP_PARTIAL_ROW")
        observations.append(
            LinkObservation(
                local_device=device.name,
                local_port_raw=local_port_raw,
                local_port_norm=local_port_norm,
                remote_device_id=row.remote_chassis,
                remote_device_name=remote_device_name,
                remote_port_raw=row.remote_port,
                remote_port_norm=remote_port_norm,
                source="lldp",
                confidence=confidence,
                errors=tuple(error_list),
            )
        )

    return DeviceCollectionResult(observations, errors)


def _resolve_device_name(raw_name: str, alias_map: dict[str, str] | None) -> str:
    """Resolve raw LLDP system name to a canonical device name."""

    if not raw_name:
        return UNKNOWN_VALUE
    if alias_map is None:
        return raw_name
    return alias_map.get(raw_name.lower(), raw_name)


def _command_exists(command: str) -> bool:
    """Check if a command exists on PATH."""

    return Path(command).is_file() or bool(shutil.which(command))


def _run_snmpwalk(
    snmpwalk_cmd: str,
    device: Device,
    timeout: int,
    retries: int,
    oid: str,
) -> list[str] | None:
    """Run snmpwalk and return output lines, or None on failure."""

    command = [
        snmpwalk_cmd,
        "-v",
        device.snmp_version,
        "-c",
        device.snmp_community or "",
        "-t",
        str(timeout),
        "-r",
        str(retries),
        device.mgmt_ip,
        oid,
    ]
    _LOGGER.debug("Running snmpwalk: %s", " ".join(command))
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        _LOGGER.error("Failed to run snmpwalk: %s", exc)
        return None

    if result.returncode != 0:
        _LOGGER.error("snmpwalk failed for %s: %s", device.name, result.stderr)
        return None

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


@dataclass(frozen=True)
class RemRow:
    """Parsed LLDP remote row."""

    local_port: str
    remote_chassis: str
    remote_port: str
    remote_sys_name: str


def _parse_loc_port_table(lines: Iterable[str]) -> dict[str, str]:
    """Parse lldpLocPortTable output into a map of port index to id."""

    port_map: dict[str, str] = {}
    pattern = re.compile(r"lldpLocPortId\.(?P<index>[\d.]+)\s*=\s*\w+:\s*(?P<value>.+)")
    for line in lines:
        match = pattern.search(line)
        if match:
            port_map[match.group("index")] = _strip_snmp_value(match.group("value"))
    return port_map


def _parse_rem_table(lines: Iterable[str]) -> list[RemRow]:
    """Parse lldpRemTable output into rows grouped by local port."""

    rows: dict[str, dict[str, str]] = {}
    patterns = {
        "remote_chassis": re.compile(
            r"lldpRemChassisId\.(?P<index>[\d.]+)\s*=\s*\w+:\s*(?P<value>.+)"
        ),
        "remote_port": re.compile(r"lldpRemPortId\.(?P<index>[\d.]+)\s*=\s*\w+:\s*(?P<value>.+)"),
        "remote_sys_name": re.compile(
            r"lldpRemSysName\.(?P<index>[\d.]+)\s*=\s*\w+:\s*(?P<value>.+)"
        ),
    }
    for line in lines:
        for key, pattern in patterns.items():
            match = pattern.search(line)
            if match:
                index = match.group("index")
                values = rows.get(index)
                if values is None:
                    values = {}
                    rows[index] = values
                values[key] = _strip_snmp_value(match.group("value"))
    rem_rows: list[RemRow] = []
    for index, values in rows.items():
        local_port = index.split(".")[1] if "." in index else index
        rem_rows.append(
            RemRow(
                local_port=local_port,
                remote_chassis=values.get("remote_chassis", UNKNOWN_VALUE),
                remote_port=values.get("remote_port", UNKNOWN_VALUE),
                remote_sys_name=values.get("remote_sys_name", UNKNOWN_VALUE),
            )
        )
    return rem_rows


def _strip_snmp_value(raw_value: str) -> str:
    """Normalize snmpwalk values by removing quotes and hex wrappers."""

    value = raw_value.strip().strip('"')
    if value.startswith("0x"):
        return value
    return value
