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
"""Filtering utilities for links and diffs."""

from __future__ import annotations

import re
from typing import Sequence

from nw_check.models import AsIsLink, LinkDiff


def filter_asis_links(
    links: list[AsIsLink],
    device_filter: Sequence[str] | None = None,
    device_regex: str | None = None,
) -> list[AsIsLink]:
    """Filter As-Is links by device name.

    Args:
        links: List of As-Is links to filter
        device_filter: List of exact device names to include
        device_regex: Regular expression pattern for device names

    Returns:
        Filtered list of links
    """

    if not device_filter and not device_regex:
        return links

    filtered: list[AsIsLink] = []
    pattern = re.compile(device_regex) if device_regex else None

    for link in links:
        if device_filter:
            if link.device_a in device_filter or link.device_b in device_filter:
                filtered.append(link)
                continue

        if pattern:
            if pattern.search(link.device_a) or pattern.search(link.device_b):
                filtered.append(link)
                continue

    return filtered


def filter_diffs(
    diffs: list[LinkDiff],
    device_filter: Sequence[str] | None = None,
    device_regex: str | None = None,
    status_filter: Sequence[str] | None = None,
) -> list[LinkDiff]:
    """Filter link diffs by device name and/or status.

    Args:
        diffs: List of link diffs to filter
        device_filter: List of exact device names to include
        device_regex: Regular expression pattern for device names
        status_filter: List of status values to include (e.g., ["PORT_MISMATCH", "MISSING_ASIS"])

    Returns:
        Filtered list of diffs
    """

    if not device_filter and not device_regex and not status_filter:
        return diffs

    filtered: list[LinkDiff] = []
    pattern = re.compile(device_regex) if device_regex else None

    for diff in diffs:
        # Check status filter first (most restrictive)
        if status_filter and diff.status not in status_filter:
            continue

        # Check device filters
        if device_filter or device_regex:
            device_match = False

            if device_filter:
                if (
                    diff.tobe_link.device_a in device_filter
                    or diff.tobe_link.device_b in device_filter
                ):
                    device_match = True

            if pattern and not device_match:
                if pattern.search(diff.tobe_link.device_a) or pattern.search(
                    diff.tobe_link.device_b
                ):
                    device_match = True

            if not device_match:
                continue

        filtered.append(diff)

    return filtered
