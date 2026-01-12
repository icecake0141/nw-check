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
"""Tests for interface normalization."""

from nw_check.normalize import normalize_interface_name


def test_normalize_interface_name_maps_prefixes() -> None:
    assert normalize_interface_name("Eth1/1") == "Eth1/1"
    assert normalize_interface_name("ethernet1/2") == "Eth1/2"
    assert normalize_interface_name("Gi1/3") == "Eth1/3"
    assert normalize_interface_name("GigabitEthernet1/4") == "Eth1/4"
    assert normalize_interface_name("Te1-1") == "Eth1/1"


def test_normalize_interface_name_handles_empty() -> None:
    assert normalize_interface_name("") == "unknown"
    assert normalize_interface_name("   ") == "unknown"
