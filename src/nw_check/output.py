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
"""Output rendering for reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from nw_check.models import UNKNOWN_VALUE, AsIsLink, LinkDiff


def write_asis_links(path: str | Path, links: list[AsIsLink]) -> None:
    """Write As-Is links CSV."""

    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "local_device",
                "local_port",
                "remote_device",
                "remote_port",
                "confidence",
                "evidence",
            ]
        )
        for link in sorted(
            links,
            key=lambda item: (item.device_a, item.port_a, item.device_b, item.port_b),
        ):
            writer.writerow(
                [
                    link.device_a,
                    link.port_a,
                    link.device_b,
                    link.port_b,
                    link.confidence,
                    ";".join(link.evidence),
                ]
            )


def write_diff_links(path: str | Path, diffs: list[LinkDiff]) -> None:
    """Write To-Be vs As-Is diff CSV."""

    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["device_a", "port_a", "device_b", "port_b", "status", "reason"])
        for diff in sorted(
            diffs,
            key=lambda item: (
                item.tobe_link.device_a,
                item.tobe_link.port_a_norm,
                item.tobe_link.device_b,
                item.tobe_link.port_b_norm,
            ),
        ):
            writer.writerow(
                [
                    diff.tobe_link.device_a,
                    diff.tobe_link.port_a_norm,
                    diff.tobe_link.device_b,
                    diff.tobe_link.port_b_norm,
                    diff.status,
                    diff.reason,
                ]
            )


def write_summary(
    path: str | Path,
    diffs: list[LinkDiff],
    errors: list[str],
    asis_links: list[AsIsLink],
) -> None:
    """Write summary report."""

    lldp_failed_devices = sorted(set(errors))
    missing_ports = sum(
        1 for link in asis_links for port in (link.port_a, link.port_b) if port == UNKNOWN_VALUE
    )
    mismatch_links = sum(1 for diff in diffs if diff.status != "EXACT_MATCH")

    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(f"lldp_failed_devices: {', '.join(lldp_failed_devices)}\n")
        handle.write(f"missing_ports: {missing_ports}\n")
        handle.write(f"mismatch_links: {mismatch_links}\n")


def write_asis_links_json(path: str | Path, links: list[AsIsLink]) -> None:
    """Write As-Is links JSON."""

    sorted_links = sorted(
        links,
        key=lambda item: (item.device_a, item.port_a, item.device_b, item.port_b),
    )
    data: list[dict[str, Any]] = [
        {
            "local_device": link.device_a,
            "local_port": link.port_a,
            "remote_device": link.device_b,
            "remote_port": link.port_b,
            "confidence": link.confidence,
            "evidence": list(link.evidence),
        }
        for link in sorted_links
    ]

    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_diff_links_json(path: str | Path, diffs: list[LinkDiff]) -> None:
    """Write To-Be vs As-Is diff JSON."""

    sorted_diffs = sorted(
        diffs,
        key=lambda item: (
            item.tobe_link.device_a,
            item.tobe_link.port_a_norm,
            item.tobe_link.device_b,
            item.tobe_link.port_b_norm,
        ),
    )
    data: list[dict[str, Any]] = [
        {
            "device_a": diff.tobe_link.device_a,
            "port_a": diff.tobe_link.port_a_norm,
            "device_b": diff.tobe_link.device_b,
            "port_b": diff.tobe_link.port_b_norm,
            "status": diff.status,
            "reason": diff.reason,
        }
        for diff in sorted_diffs
    ]

    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_summary_json(
    path: str | Path,
    diffs: list[LinkDiff],
    errors: list[str],
    asis_links: list[AsIsLink],
) -> None:
    """Write summary report JSON."""

    lldp_failed_devices = sorted(set(errors))
    missing_ports = sum(
        1 for link in asis_links for port in (link.port_a, link.port_b) if port == UNKNOWN_VALUE
    )
    mismatch_links = sum(1 for diff in diffs if diff.status != "EXACT_MATCH")

    data = {
        "lldp_failed_devices": lldp_failed_devices,
        "missing_ports": missing_ports,
        "mismatch_links": mismatch_links,
    }

    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
