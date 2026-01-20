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

import json
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

# Supported SNMPv3 authentication protocols (as per snmpwalk -a option)
SUPPORTED_AUTH_PROTOCOLS = {
    "md5": "MD5",
    "sha": "SHA",
    "sha1": "SHA",  # SHA-1 is typically just called SHA
    "sha-224": "SHA-224",
    "sha224": "SHA-224",
    "sha-256": "SHA-256",
    "sha256": "SHA-256",
    "sha-384": "SHA-384",
    "sha384": "SHA-384",
    "sha-512": "SHA-512",
    "sha512": "SHA-512",
}

# Supported SNMPv3 privacy protocols (as per snmpwalk -x option)
SUPPORTED_PRIV_PROTOCOLS = {
    "des": "DES",
    "aes": "AES",
    "aes128": "AES",  # AES and AES-128 are equivalent
    "aes-128": "AES",
    "aes-192": "AES-192",
    "aes192": "AES-192",
    "aes-256": "AES-256",
    "aes256": "AES-256",
}


@dataclass(frozen=True)
class DeviceCollectionResult:
    """Result of collecting LLDP information from a single device."""

    observations: list[LinkObservation]
    errors: list[str]


# pylint: disable=too-many-arguments,too-many-positional-arguments
def collect_lldp_observations(
    devices: Iterable[Device],
    timeout: int,
    retries: int,
    alias_map: dict[str, str] | None = None,
    snmpwalk_cmd: str = "snmpwalk",
    verbose: bool = False,
    show_progress: bool = False,
) -> tuple[list[LinkObservation], list[str]]:
    """Collect LLDP neighbor data from devices via SNMP walk."""

    all_observations: list[LinkObservation] = []
    failed_devices: list[str] = []
    devices_list = list(devices)
    total = len(devices_list)

    for idx, device in enumerate(devices_list, start=1):
        if show_progress:
            # Show percentage at start of device processing (idx-1 devices completed)
            percentage = ((idx - 1) * 100) // total if total > 0 else 0
            _LOGGER.info(
                "Progress: [%d/%d, %d%%] Collecting from %s",
                idx,
                total,
                percentage,
                device.name,
            )
        result = _collect_for_device(device, timeout, retries, alias_map, snmpwalk_cmd, verbose)
        all_observations.extend(result.observations)
        if result.errors:
            failed_devices.append(device.name)

        if show_progress:
            obs_count = len(result.observations)
            total_obs_count = len(all_observations)
            if result.errors:
                _LOGGER.info(
                    "  └─ Device %s: Failed with errors: %s",
                    device.name,
                    ", ".join(result.errors),
                )
            else:
                _LOGGER.info(
                    "  └─ Device %s: Collected %d observations (total: %d)",
                    device.name,
                    obs_count,
                    total_obs_count,
                )

    if show_progress and total > 0:
        _LOGGER.info("Collection complete: %d/%d devices processed", total, total)
        _LOGGER.info("Total observations collected: %d", len(all_observations))
        if failed_devices:
            _LOGGER.info("Failed devices (%d): %s", len(failed_devices), ", ".join(failed_devices))

    return all_observations, failed_devices


# pylint: disable=too-many-arguments,too-many-positional-arguments
def _collect_for_device(
    device: Device,
    timeout: int,
    retries: int,
    alias_map: dict[str, str] | None,
    snmpwalk_cmd: str,
    verbose: bool,
) -> DeviceCollectionResult:
    """Collect LLDP data for a single device using snmpwalk."""

    _LOGGER.debug("Starting LLDP collection for device: %s (IP: %s)", device.name, device.mgmt_ip)
    errors: list[str] = []
    if not _validate_snmp_credentials(device):
        _LOGGER.warning("SNMP credentials invalid for %s", device.name)
        errors.append("SNMP_AUTH_FAILED")
        return DeviceCollectionResult([], errors)

    if not _command_exists(snmpwalk_cmd):
        _LOGGER.error("snmpwalk command not found: %s", snmpwalk_cmd)
        errors.append("SNMP_COMMAND_MISSING")
        return DeviceCollectionResult([], errors)

    _LOGGER.debug("Collecting local port table for %s", device.name)
    loc_port_result = _run_snmpwalk(
        snmpwalk_cmd,
        device,
        timeout,
        retries,
        LLDP_LOC_PORT_TABLE,
        verbose,
    )
    if loc_port_result.error:
        _LOGGER.debug("Local port table collection failed: %s", loc_port_result.error)
        errors.append(loc_port_result.error)
        return DeviceCollectionResult([], errors)

    _LOGGER.debug("Collecting remote neighbor table for %s", device.name)
    rem_result = _run_snmpwalk(snmpwalk_cmd, device, timeout, retries, LLDP_REM_TABLE, verbose)
    if rem_result.error:
        _LOGGER.debug("Remote table collection failed: %s", rem_result.error)
        errors.append(rem_result.error)
        return DeviceCollectionResult([], errors)

    _LOGGER.debug("Parsing local port table (%d lines)", len(loc_port_result.lines))
    loc_ports = _parse_loc_port_table(loc_port_result.lines)
    _LOGGER.debug("Parsed %d local ports", len(loc_ports))

    _LOGGER.debug("Parsing remote neighbor table (%d lines)", len(rem_result.lines))
    rem_rows = _parse_rem_table(rem_result.lines)
    _LOGGER.debug("Parsed %d remote neighbor rows", len(rem_rows))

    if not rem_rows:
        _LOGGER.debug("LLDP remote table empty for %s", device.name)
        errors.append("LLDP_TABLE_EMPTY")
        return DeviceCollectionResult([], errors)

    observations: list[LinkObservation] = []
    for row in rem_rows:
        local_port_raw = loc_ports.get(row.local_port) or UNKNOWN_VALUE
        local_port_norm = normalize_interface_name(local_port_raw)
        remote_port_norm = normalize_interface_name(row.remote_port)
        remote_device_name = _resolve_device_name(row.remote_sys_name, alias_map)

        _LOGGER.debug(
            "Processing LLDP observation: %s[%s->%s] -> %s[%s->%s] (chassis: %s, sysname: %s)",
            device.name,
            local_port_raw,
            local_port_norm,
            remote_device_name,
            row.remote_port,
            remote_port_norm,
            row.remote_chassis,
            row.remote_sys_name,
        )

        confidence = "observed"
        error_list: list[str] = []
        if UNKNOWN_VALUE in (remote_device_name, row.remote_port):
            confidence = "partial"
            error_list.append("LLDP_PARTIAL_ROW")
            _LOGGER.debug(
                "Partial observation detected (device=%s, port=%s)",
                remote_device_name,
                row.remote_port,
            )

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

    _LOGGER.debug("Collected %d observations from %s", len(observations), device.name)
    return DeviceCollectionResult(observations, errors)


def _resolve_device_name(raw_name: str, alias_map: dict[str, str] | None) -> str:
    """Resolve raw LLDP system name to a canonical device name."""

    if not raw_name:
        _LOGGER.debug("Empty remote system name, returning UNKNOWN")
        return UNKNOWN_VALUE
    if alias_map is None:
        _LOGGER.debug("No alias map provided, using raw name: %s", raw_name)
        return raw_name

    resolved = alias_map.get(raw_name.lower(), raw_name)
    if resolved != raw_name:
        _LOGGER.debug("Resolved device name '%s' -> '%s' via alias map", raw_name, resolved)
    else:
        _LOGGER.debug("Device name '%s' not found in alias map, using as-is", raw_name)

    return resolved


def _command_exists(command: str) -> bool:
    """Check if a command exists on PATH."""

    return Path(command).is_file() or bool(shutil.which(command))


def _normalize_snmpv3_protocol(protocol: str, protocol_type: str) -> str | None:
    """Normalize and validate SNMPv3 auth or priv protocol name.

    Args:
        protocol: Raw protocol name from config (e.g., "sha", "SHA", "aes128")
        protocol_type: Either "auth" or "priv" to determine which whitelist to use

    Returns:
        Normalized protocol name for snmpwalk, or None if unsupported
    """
    normalized_input = protocol.lower().strip()

    if protocol_type == "auth":
        return SUPPORTED_AUTH_PROTOCOLS.get(normalized_input)
    if protocol_type == "priv":
        return SUPPORTED_PRIV_PROTOCOLS.get(normalized_input)

    return None


# pylint: disable=too-many-return-statements
def _validate_snmp_credentials(device: Device) -> bool:
    """Validate SNMP credentials for the configured version."""

    version = device.snmp_version.strip().lower()
    if version in {"3", "v3"}:
        if not device.snmp_user:
            return False
        auth = _parse_snmpv3_credential(device.snmp_auth)
        priv = _parse_snmpv3_credential(device.snmp_priv)

        # Validate authPriv combinations
        if priv and not auth:
            return False
        if device.snmp_auth and not auth:
            return False
        if device.snmp_priv and not priv:
            return False

        # Validate auth protocol if present
        if auth:
            auth_protocol, _ = auth
            normalized_auth = _normalize_snmpv3_protocol(auth_protocol, "auth")
            if normalized_auth is None:
                _LOGGER.error(
                    "Unsupported auth protocol '%s' for device %s. "
                    "Supported: MD5, SHA, SHA-224, SHA-256, SHA-384, SHA-512",
                    auth_protocol,
                    device.name,
                )
                return False

        # Validate priv protocol if present
        if priv:
            priv_protocol, _ = priv
            normalized_priv = _normalize_snmpv3_protocol(priv_protocol, "priv")
            if normalized_priv is None:
                _LOGGER.error(
                    "Unsupported priv protocol '%s' for device %s. "
                    "Supported: DES, AES, AES-192, AES-256",
                    priv_protocol,
                    device.name,
                )
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
        auth_protocol, auth_secret = auth
        # Normalize the auth protocol name
        normalized_auth = _normalize_snmpv3_protocol(auth_protocol, "auth")
        # Use normalized protocol or fall back to original (validation should catch invalid ones)
        args.extend(["-a", normalized_auth or auth_protocol, "-A", auth_secret])
    if priv:
        priv_protocol, priv_secret = priv
        # Normalize the priv protocol name
        normalized_priv = _normalize_snmpv3_protocol(priv_protocol, "priv")
        # Use normalized protocol or fall back to original (validation should catch invalid ones)
        args.extend(["-x", normalized_priv or priv_protocol, "-X", priv_secret])
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


# pylint: disable=too-many-arguments,too-many-positional-arguments
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
        # Extract local port from lldpRemTable index: timeMark.localPortNum.remoteIndex
        # For modular switches, localPortNum can be multi-part (e.g., "1.49")
        parts = index.split(".")
        if len(parts) >= 3:
            # Extract everything between first (timeMark) and last (remoteIndex)
            local_port = ".".join(parts[1:-1])
        elif len(parts) == 2:
            # Simple case: timeMark.localPortNum (no remoteIndex)
            local_port = parts[1]
        else:
            # No dots in index, use as-is
            local_port = index
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


def save_observations(path: str | Path, observations: list[LinkObservation]) -> None:
    """Save link observations to a JSON file for dry-run mode."""

    data = [
        {
            "local_device": obs.local_device,
            "local_port_raw": obs.local_port_raw,
            "local_port_norm": obs.local_port_norm,
            "remote_device_id": obs.remote_device_id,
            "remote_device_name": obs.remote_device_name,
            "remote_port_raw": obs.remote_port_raw,
            "remote_port_norm": obs.remote_port_norm,
            "source": obs.source,
            "confidence": obs.confidence,
            "errors": list(obs.errors),
        }
        for obs in observations
    ]

    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_observations(path: str | Path) -> list[LinkObservation]:
    """Load link observations from a JSON file for dry-run mode."""

    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    observations = [
        LinkObservation(
            local_device=item["local_device"],
            local_port_raw=item["local_port_raw"],
            local_port_norm=item["local_port_norm"],
            remote_device_id=item["remote_device_id"],
            remote_device_name=item["remote_device_name"],
            remote_port_raw=item["remote_port_raw"],
            remote_port_norm=item["remote_port_norm"],
            source=item["source"],
            confidence=item["confidence"],
            errors=tuple(item.get("errors", [])),
        )
        for item in data
    ]

    return observations
