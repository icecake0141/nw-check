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
"""Normalization utilities."""

from __future__ import annotations

import re

from nw_check.models import UNKNOWN_VALUE

_PREFIX_MAP: tuple[tuple[str, str], ...] = (
    (r"^ethernet", "Eth"),
    (r"^eth", "Eth"),
    (r"^gigabitethernet", "Eth"),
    (r"^gigabit", "Eth"),
    (r"^gi", "Eth"),
    (r"^tengigabitethernet", "Eth"),
    (r"^tengigabit", "Eth"),
    (r"^te", "Eth"),
)


def normalize_interface_name(raw_name: str) -> str:
    """Normalize interface names to a canonical form."""

    if not raw_name:
        return UNKNOWN_VALUE

    cleaned = re.sub(r"\s+", "", raw_name.strip())
    if not cleaned:
        return UNKNOWN_VALUE

    normalized = cleaned.replace("-", "/")
    lowered = normalized.lower()
    for pattern, prefix in _PREFIX_MAP:
        match = re.match(pattern, lowered)
        if match:
            suffix = normalized[match.end() :]
            return f"{prefix}{suffix}"

    return normalized
