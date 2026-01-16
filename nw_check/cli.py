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
"""CLI entrypoint."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from nw_check.diff import diff_links
from nw_check.inventory import (
    build_device_alias_map,
    load_device_inventory,
    load_link_intents,
)
from nw_check.link_infer import deduplicate_links
from nw_check.lldp_snmp import collect_lldp_observations
from nw_check.output import (
    write_asis_links,
    write_asis_links_json,
    write_diff_links,
    write_diff_links_json,
    write_summary,
    write_summary_json,
)

_LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""

    parser = argparse.ArgumentParser(description="nw-check")
    parser.add_argument("--devices", required=True, help="path to device inventory CSV")
    parser.add_argument("--tobe", required=True, help="path to To-Be wiring CSV")
    parser.add_argument("--out-dir", required=True, help="output directory")
    parser.add_argument("--snmp-timeout", type=int, default=2, help="SNMP timeout seconds")
    parser.add_argument("--snmp-retries", type=int, default=1, help="SNMP retries")
    parser.add_argument(
        "--snmp-verbose",
        action="store_true",
        help="enable verbose SNMP command logging (redacted secrets)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["INFO", "DEBUG", "WARN"],
        help="log level",
    )
    parser.add_argument(
        "--output-format",
        default="csv",
        choices=["csv", "json", "both"],
        help="output format (default: csv)",
    )
    return parser


def configure_logging(level: str) -> None:
    """Configure logging."""

    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s %(message)s")


def main() -> int:
    """Run nw-check."""

    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        devices = load_device_inventory(args.devices)
        tobe_links = load_link_intents(args.tobe)
    except ValueError as exc:
        _LOGGER.error("Invalid input: %s", exc)
        return 3
    alias_map = build_device_alias_map(devices)

    observations, errors = collect_lldp_observations(
        devices=devices,
        timeout=args.snmp_timeout,
        retries=args.snmp_retries,
        alias_map=alias_map,
        verbose=args.snmp_verbose,
    )
    _LOGGER.info("Collected %s observations", len(observations))

    asis_links = deduplicate_links(observations)
    diffs = diff_links(tobe_links, asis_links)

    # Write outputs based on format
    if args.output_format in ("csv", "both"):
        write_asis_links(out_dir / "asis_links.csv", asis_links)
        write_diff_links(out_dir / "diff_links.csv", diffs)
        write_summary(out_dir / "summary.txt", diffs, errors, asis_links)

    if args.output_format in ("json", "both"):
        write_asis_links_json(out_dir / "asis_links.json", asis_links)
        write_diff_links_json(out_dir / "diff_links.json", diffs)
        write_summary_json(out_dir / "summary.json", diffs, errors, asis_links)

    if errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
