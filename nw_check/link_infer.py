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
"""Link inference and deduplication."""

from __future__ import annotations

from collections import defaultdict

from nw_check.models import UNKNOWN_VALUE, AsIsLink, LinkObservation


def deduplicate_links(observations: list[LinkObservation]) -> list[AsIsLink]:
    """Deduplicate directional observations into undirected links."""

    grouped: dict[tuple[str, str, str, str], list[LinkObservation]] = defaultdict(list)
    for obs in observations:
        remote_device = (
            obs.remote_device_id
            if obs.remote_device_name == UNKNOWN_VALUE
            else obs.remote_device_name
        )
        device_a, port_a, device_b, port_b = _canonicalize(
            obs.local_device,
            obs.local_port_norm,
            remote_device,
            obs.remote_port_norm,
        )
        grouped[(device_a, port_a, device_b, port_b)].append(obs)

    deduped: list[AsIsLink] = []
    for (device_a, port_a, device_b, port_b), obs_list in grouped.items():
        confidence = _merge_confidence(obs_list)
        evidence = sorted({obs.source for obs in obs_list})
        deduped.append(
            AsIsLink(
                device_a=device_a,
                port_a=port_a,
                device_b=device_b,
                port_b=port_b,
                confidence=confidence,
                evidence=tuple(evidence),
            )
        )

    return sorted(
        deduped, key=lambda link: (link.device_a, link.port_a, link.device_b, link.port_b)
    )


def _canonicalize(
    device_a: str,
    port_a: str,
    device_b: str,
    port_b: str,
) -> tuple[str, str, str, str]:
    """Canonicalize link endpoints for deduplication."""

    device_a = device_a or UNKNOWN_VALUE
    device_b = device_b or UNKNOWN_VALUE
    port_a = port_a or UNKNOWN_VALUE
    port_b = port_b or UNKNOWN_VALUE
    left = (device_a, port_a)
    right = (device_b, port_b)
    if left <= right:
        return device_a, port_a, device_b, port_b
    return device_b, port_b, device_a, port_a


def _merge_confidence(observations: list[LinkObservation]) -> str:
    """Merge confidence across observations."""

    confidences = {obs.confidence for obs in observations}
    if "observed" in confidences and len(observations) > 1:
        return "observed"
    if "partial" in confidences:
        return "partial"
    return "unknown"
