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
from pathlib import Path

from nw_check.models import AsIsLink, LinkDiff


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


def write_summary(path: str | Path, diffs: list[LinkDiff], errors: list[str]) -> None:
    """Write summary report."""

    lldp_failed_devices = sorted({error for error in errors})
    missing_ports = sum(1 for diff in diffs if diff.status == "PARTIAL_OBSERVED")
    mismatch_links = sum(1 for diff in diffs if diff.status != "EXACT_MATCH")

    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(f"lldp_failed_devices: {', '.join(lldp_failed_devices)}\n")
        handle.write(f"missing_ports: {missing_ports}\n")
        handle.write(f"mismatch_links: {mismatch_links}\n")
