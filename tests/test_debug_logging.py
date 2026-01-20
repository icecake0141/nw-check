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
"""Tests for debug logging functionality."""

import logging
import os
from unittest.mock import patch

from nw_check.cli import configure_logging


def test_configure_logging_default() -> None:
    """Test default logging configuration."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    configure_logging("INFO", debug=False)
    
    assert logger.level == logging.INFO


def test_configure_logging_debug_flag() -> None:
    """Test debug logging enabled via flag."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    configure_logging("INFO", debug=True)
    
    assert logger.level == logging.DEBUG


def test_configure_logging_debug_env_var() -> None:
    """Test debug logging enabled via environment variable."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    with patch.dict(os.environ, {"NW_CHECK_DEBUG": "1"}):
        configure_logging("INFO", debug=False)
        
        assert logger.level == logging.DEBUG


def test_configure_logging_debug_env_var_true() -> None:
    """Test debug logging enabled via environment variable with 'true'."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    with patch.dict(os.environ, {"NW_CHECK_DEBUG": "true"}):
        configure_logging("INFO", debug=False)
        
        assert logger.level == logging.DEBUG


def test_configure_logging_debug_env_var_yes() -> None:
    """Test debug logging enabled via environment variable with 'yes'."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    with patch.dict(os.environ, {"NW_CHECK_DEBUG": "yes"}):
        configure_logging("INFO", debug=False)
        
        assert logger.level == logging.DEBUG


def test_configure_logging_debug_env_var_ignored_when_false() -> None:
    """Test debug logging not enabled when env var is not truthy."""
    # Reset root logger to ensure clean state
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    
    with patch.dict(os.environ, {"NW_CHECK_DEBUG": "0"}):
        configure_logging("INFO", debug=False)
        
        assert logger.level == logging.INFO

