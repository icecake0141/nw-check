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
    verbose: bool = False,
) -> tuple[list[LinkObservation], list[str]]:
    """Collect LLDP neighbor data from devices via SNMP walk."""

    all_observations: list[LinkObservation] = []
    failed_devices: list[str] = []
    for device in devices:
        result = _collect_for_device(device, timeout, retries, alias_map, snmpwalk_cmd, verbose)
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
    verbose: bool,
) -> DeviceCollectionResult:
    """Collect LLDP data for a single device using snmpwalk."""

    errors: list[str] = []
    if not _validate_snmp_credentials(device):
        _LOGGER.warning("SNMP credentials invalid for %s", device.name)
        errors.append("SNMP_AUTH_FAILED")
        return DeviceCollectionResult([], errors)

    if not _command_exists(snmpwalk_cmd):
        _LOGGER.error("snmpwalk command not found: %s", snmpwalk_cmd)
        errors.append("SNMP_COMMAND_MISSING")
        return DeviceCollectionResult([], errors)

    loc_port_result = _run_snmpwalk(
        snmpwalk_cmd,
        device,
        timeout,
        retries,
        LLDP_LOC_PORT_TABLE,
        verbose,
    )
    if loc_port_result.error:
        errors.append(loc_port_result.error)
        return DeviceCollectionResult([], errors)

    rem_result = _run_snmpwalk(snmpwalk_cmd, device, timeout, retries, LLDP_REM_TABLE, verbose)
    if rem_result.error:
        errors.append(rem_result.error)
        return DeviceCollectionResult([], errors)

    loc_ports = _parse_loc_port_table(loc_port_result.lines)
    rem_rows = _parse_rem_table(rem_result.lines)
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
        if UNKNOWN_VALUE in (remote_device_name, row.remote_port):
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


def _validate_snmp_credentials(device: Device) -> bool:
    """Validate SNMP credentials for the configured version."""

    version = device.snmp_version.strip().lower()
    if version in {"3", "v3"}:
        if not device.snmp_user:
            return False
        auth = _parse_snmpv3_credential(device.snmp_auth)
        priv = _parse_snmpv3_credential(device.snmp_priv)
        if priv and not auth:
            return False
        if device.snmp_auth and not auth:
            return False
        if device.snmp_priv and not priv:
            return False
        return True
    return bool(device.snmp_community)


def _build_snmpwalk_command(
    snmpwalk_cmd: str,
    device: Device,
    timeout: int,
    retries: int,
    oid: str,
) -> list[str]:
    """Build a snmpwalk command list based on device credentials."""

    version_raw = device.snmp_version.strip().lower()
    if version_raw in {"v1"}:
        version = "1"
    elif version_raw in {"v2c"}:
        version = "2c"
    elif version_raw in {"v3"}:
        version = "3"
    else:
        version = device.snmp_version.strip()
    command = [
        snmpwalk_cmd,
        "-v",
        version,
        "-t",
        str(timeout),
        "-r",
        str(retries),
    ]

    if version_raw in {"3", "v3"}:
        command.extend(_snmpv3_args(device))
    else:
        command.extend(["-c", device.snmp_community or ""])

    command.extend([device.mgmt_ip, oid])
    return command


def _snmpv3_args(device: Device) -> list[str]:
    """Build SNMPv3 auth/priv arguments for snmpwalk."""

    auth = _parse_snmpv3_credential(device.snmp_auth)
    priv = _parse_snmpv3_credential(device.snmp_priv)
    if priv and auth:
        level = "authPriv"
    elif auth:
        level = "authNoPriv"
    else:
        level = "noAuthNoPriv"

    args = ["-l", level, "-u", device.snmp_user or ""]
    if auth:
        args.extend(["-a", auth[0], "-A", auth[1]])
    if priv:
        args.extend(["-x", priv[0], "-X", priv[1]])
    return args


def _parse_snmpv3_credential(raw: str | None) -> tuple[str, str] | None:
    """Parse SNMPv3 credential fields in the form protocol:secret."""

    if not raw:
        return None
    parts = raw.split(":", 1)
    if len(parts) != 2:
        return None
    protocol, secret = (part.strip() for part in parts)
    if not protocol or not secret:
        return None
    return protocol, secret


def _run_snmpwalk(
    snmpwalk_cmd: str,
    device: Device,
    timeout: int,
    retries: int,
    oid: str,
    verbose: bool,
) -> "SnmpwalkResult":
    """Run snmpwalk and return output lines plus error classification."""

    command = _build_snmpwalk_command(snmpwalk_cmd, device, timeout, retries, oid)
    redacted_command = _redact_snmp_command(command)
    log_message = " ".join(redacted_command)
    if verbose:
        _LOGGER.info("Running snmpwalk: %s", log_message)
    else:
        _LOGGER.debug("Running snmpwalk: %s", log_message)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        _LOGGER.error("Failed to run snmpwalk: %s", exc)
        return SnmpwalkResult([], "SNMP_COMMAND_FAILED")

    if result.returncode != 0:
        combined_output = "\n".join([result.stdout, result.stderr]).strip()
        error_code = _classify_snmpwalk_error(combined_output)
        if verbose:
            _LOGGER.warning(
                "snmpwalk failed for %s (%s). stderr=%s",
                device.name,
                error_code,
                result.stderr.strip() or "<empty>",
            )
        else:
            _LOGGER.error("snmpwalk failed for %s (%s)", device.name, error_code)
        return SnmpwalkResult([], error_code)

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if verbose:
        _LOGGER.info("snmpwalk succeeded for %s (%s lines)", device.name, len(lines))
    return SnmpwalkResult(lines, None)


@dataclass(frozen=True)
class SnmpwalkResult:
    """Result of running snmpwalk."""

    lines: list[str]
    error: str | None


def _redact_snmp_command(command: list[str]) -> list[str]:
    """Redact secrets from an snmpwalk command for logging."""

    redacted = command.copy()
    secret_flags = {"-c", "-A", "-X"}
    for index, token in enumerate(redacted[:-1]):
        if token in secret_flags:
            redacted[index + 1] = "******"
    return redacted


def _classify_snmpwalk_error(output: str) -> str:
    """Classify snmpwalk error output into a stable error code."""

    lowered = output.lower()
    auth_markers = (
        "authentication failure",
        "authorization error",
        "unknown user name",
        "wrong community",
    )
    if any(marker in lowered for marker in auth_markers):
        return "SNMP_AUTH_FAILED"

    mib_markers = (
        "unknown object identifier",
        "no such object",
        "no such instance",
        "cannot find module",
        "mib not found",
    )
    if any(marker in lowered for marker in mib_markers):
        return "SNMP_MIB_MISSING"

    reachability_markers = (
        "timeout",
        "no response",
        "no route to host",
        "network is unreachable",
        "connection refused",
        "host is down",
    )
    if any(marker in lowered for marker in reachability_markers):
        return "SNMP_TARGET_UNREACHABLE"

    return "SNMP_UNKNOWN_ERROR"


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
