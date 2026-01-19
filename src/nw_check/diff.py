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
"""To-Be vs As-Is diff logic."""

from __future__ import annotations

from nw_check.models import UNKNOWN_VALUE, AsIsLink, LinkDiff, LinkIntent

STATUS_EXACT_MATCH = "EXACT_MATCH"
STATUS_PORT_MISMATCH = "PORT_MISMATCH"
STATUS_DEVICE_MISMATCH = "DEVICE_MISMATCH"
STATUS_MISSING_ASIS = "MISSING_ASIS"
STATUS_PARTIAL_OBSERVED = "PARTIAL_OBSERVED"
STATUS_UNKNOWN = "UNKNOWN"


def diff_links(tobe_links: list[LinkIntent], asis_links: list[AsIsLink]) -> list[LinkDiff]:
    """Compare To-Be links against As-Is links."""

    asis_by_key = {
        _canonical_key(link.device_a, link.port_a, link.device_b, link.port_b): link
        for link in asis_links
    }

    diff_results: list[LinkDiff] = []
    for intent in tobe_links:
        key = _canonical_key(
            intent.device_a,
            intent.port_a_norm,
            intent.device_b,
            intent.port_b_norm,
        )
        exact = asis_by_key.get(key)
        if exact:
            diff_results.append(
                LinkDiff(
                    tobe_link=intent,
                    asis_link=exact,
                    status=STATUS_EXACT_MATCH,
                    reason="normalized ports matched",
                )
            )
            continue

        candidates = _find_candidates(intent, asis_links)
        if len(candidates) > 1:
            diff_results.append(
                LinkDiff(
                    tobe_link=intent,
                    asis_link=None,
                    status=STATUS_UNKNOWN,
                    reason=_format_candidates(candidates),
                )
            )
            continue

        if candidates:
            candidate = candidates[0]
            if _is_partial(candidate):
                diff_results.append(
                    LinkDiff(
                        tobe_link=intent,
                        asis_link=candidate,
                        status=STATUS_PARTIAL_OBSERVED,
                        reason=_partial_reason(candidate),
                    )
                )
                continue

        if _has_device_match(intent, asis_links):
            reason = _port_mismatch_reason(intent, asis_links)
            diff_results.append(
                LinkDiff(
                    tobe_link=intent,
                    asis_link=None,
                    status=STATUS_PORT_MISMATCH,
                    reason=reason,
                )
            )
            continue

        if _has_port_match(intent, asis_links):
            reason = _device_mismatch_reason(intent, asis_links)
            diff_results.append(
                LinkDiff(
                    tobe_link=intent,
                    asis_link=None,
                    status=STATUS_DEVICE_MISMATCH,
                    reason=reason,
                )
            )
            continue

        diff_results.append(
            LinkDiff(
                tobe_link=intent,
                asis_link=None,
                status=STATUS_MISSING_ASIS,
                reason="no lldp observation",
            )
        )

    return diff_results


def _canonical_key(
    device_a: str, port_a: str, device_b: str, port_b: str
) -> tuple[str, str, str, str]:
    """Canonicalize key for undirected matching."""

    left = (device_a, port_a)
    right = (device_b, port_b)
    if left <= right:
        return device_a, port_a, device_b, port_b
    return device_b, port_b, device_a, port_a


def _find_candidates(intent: LinkIntent, asis_links: list[AsIsLink]) -> list[AsIsLink]:
    """Find partial candidates for a To-Be link."""

    candidates: list[AsIsLink] = []
    for link in asis_links:
        devices_match = {intent.device_a, intent.device_b} == {
            link.device_a,
            link.device_b,
        }
        ports_match = {intent.port_a_norm, intent.port_b_norm} == {
            link.port_a,
            link.port_b,
        }
        if devices_match or ports_match:
            candidates.append(link)
            continue
        if UNKNOWN_VALUE in {link.device_a, link.device_b, link.port_a, link.port_b}:
            device_overlap = intent.device_a in {
                link.device_a,
                link.device_b,
            } or intent.device_b in {
                link.device_a,
                link.device_b,
            }
            port_overlap = intent.port_a_norm in {
                link.port_a,
                link.port_b,
            } or intent.port_b_norm in {
                link.port_a,
                link.port_b,
            }
            if device_overlap or port_overlap:
                candidates.append(link)
    return candidates


def _format_candidates(candidates: list[AsIsLink]) -> str:
    """Format candidate list for UNKNOWN reason."""

    details = ", ".join(
        f"{link.device_a}:{link.port_a}-{link.device_b}:{link.port_b}" for link in candidates
    )
    return f"multiple candidates: {details}"


def _is_partial(link: AsIsLink) -> bool:
    """Check if a link is partially observed."""

    return link.confidence == "partial" or UNKNOWN_VALUE in {
        link.device_a,
        link.device_b,
        link.port_a,
        link.port_b,
    }


def _partial_reason(candidate: AsIsLink) -> str:
    """Build a reason string for partial observations."""

    details = _format_candidates([candidate])
    return f"partial LLDP observation: {details}"


def _has_device_match(intent: LinkIntent, asis_links: list[AsIsLink]) -> bool:
    """Check if any As-Is link matches the devices."""

    target = {intent.device_a, intent.device_b}
    return any({link.device_a, link.device_b} == target for link in asis_links)


def _has_port_match(intent: LinkIntent, asis_links: list[AsIsLink]) -> bool:
    """Check if any As-Is link matches the ports."""

    target = {intent.port_a_norm, intent.port_b_norm}
    return any({link.port_a, link.port_b} == target for link in asis_links)


def _port_mismatch_reason(intent: LinkIntent, asis_links: list[AsIsLink]) -> str:
    """Build a PORT_MISMATCH reason string."""

    matches = [
        link
        for link in asis_links
        if {link.device_a, link.device_b} == {intent.device_a, intent.device_b}
    ]
    ports = ", ".join(f"{link.port_a}-{link.port_b}" for link in matches)
    return f"remote port differs: {ports}" if ports else "remote port differs"


def _device_mismatch_reason(intent: LinkIntent, asis_links: list[AsIsLink]) -> str:
    """Build a DEVICE_MISMATCH reason string."""

    matches = [
        link
        for link in asis_links
        if {link.port_a, link.port_b} == {intent.port_a_norm, intent.port_b_norm}
    ]
    devices = ", ".join(f"{link.device_a}-{link.device_b}" for link in matches)
    return f"remote device differs: {devices}" if devices else "remote device differs"
