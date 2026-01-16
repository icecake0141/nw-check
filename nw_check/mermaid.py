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
"""Mermaid diagram generation for network topology visualization."""

from __future__ import annotations

import logging
from pathlib import Path

from nw_check.models import AsIsLink, LinkDiff

_LOGGER = logging.getLogger(__name__)


def generate_mermaid_diagram(
    asis_links: list[AsIsLink],
    diffs: list[LinkDiff] | None = None,
    max_nodes: int = 50,
) -> str:
    """Generate Mermaid graph diagram from As-Is links.

    Args:
        asis_links: List of As-Is links to visualize
        diffs: Optional list of diffs to color-code links by status
        max_nodes: Maximum number of nodes to include (default: 50)

    Returns:
        Mermaid diagram as a string
    """

    # Collect unique devices
    devices = set()
    for link in asis_links:
        devices.add(link.device_a)
        devices.add(link.device_b)

    # Remove 'unknown' devices
    devices.discard("unknown")

    if len(devices) > max_nodes:
        _LOGGER.warning(
            "Too many devices (%d) for Mermaid diagram (max: %d). "
            "Truncating to first %d devices alphabetically. "
            "Consider using filtering options to select specific devices.",
            len(devices),
            max_nodes,
            max_nodes,
        )
        # Take first max_nodes devices alphabetically
        # Note: This is a simple truncation strategy. For better control,
        # use --filter-devices or --filter-devices-regex to select specific devices.
        devices = set(sorted(devices)[:max_nodes])

    # Build status map from diffs if provided
    status_map: dict[tuple[str, str, str, str], str] = {}
    if diffs:
        for diff in diffs:
            key = (
                diff.tobe_link.device_a,
                diff.tobe_link.port_a_norm,
                diff.tobe_link.device_b,
                diff.tobe_link.port_b_norm,
            )
            status_map[key] = diff.status

    # Generate diagram
    lines = ["graph LR"]

    # Add links
    for link in asis_links:
        if link.device_a not in devices or link.device_b not in devices:
            continue

        # Format link with ports
        label = f"{link.port_a} -- {link.port_b}"
        device_a_id = _sanitize_id(link.device_a)
        device_b_id = _sanitize_id(link.device_b)
        link_line = (
            f'    {device_a_id}["{link.device_a}"] -->|{label}| {device_b_id}["{link.device_b}"]'
        )

        lines.append(link_line)

    # Add styling based on status
    if diffs:
        lines.append("")
        lines.append("    %% Styling")
        for device in sorted(devices):
            device_id = _sanitize_id(device)
            # Check if device has any mismatches
            has_mismatch = any(
                diff.status != "EXACT_MATCH"
                and device in (diff.tobe_link.device_a, diff.tobe_link.device_b)
                for diff in diffs
            )
            if has_mismatch:
                lines.append(f"    style {device_id} fill:#ffcccc")
            else:
                lines.append(f"    style {device_id} fill:#ccffcc")

    return "\n".join(lines)


def _sanitize_id(device_name: str) -> str:
    """Sanitize device name for use as Mermaid node ID."""
    # Replace special characters with underscores
    return device_name.replace("-", "_").replace(".", "_").replace("/", "_")


def write_mermaid_diagram(
    path: str | Path,
    asis_links: list[AsIsLink],
    diffs: list[LinkDiff] | None = None,
    max_nodes: int = 50,
) -> None:
    """Write Mermaid diagram to a file."""

    diagram = generate_mermaid_diagram(asis_links, diffs, max_nodes)

    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(diagram)
        handle.write("\n")

    _LOGGER.info("Mermaid diagram written to %s", path)
