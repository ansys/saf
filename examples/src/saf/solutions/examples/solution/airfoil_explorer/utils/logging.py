# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared logging utilities for StepModel transactions."""

from __future__ import annotations

from logging import DEBUG, FileHandler, Formatter, Handler, Logger, LogRecord, getLogger
import os
from pathlib import Path

from ansys.saf.glow._core.transaction import transaction_local

# Standard log format matching LogsSupervisor's expected format
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(module)s - %(message)s"


class FlushingFileHandler(FileHandler):
    """FileHandler that flushes after each log entry.

    This ensures that log data is immediately written to disk, which is critical for:
    - Tests that read log files immediately after transactions
    - Real-time log monitoring (LogsSupervisor)
    - Preventing data loss if the process crashes

    By flushing after each emit, we guarantee that log entries are available
    for reading immediately after they're logged, without requiring explicit
    flush calls or waiting for buffer fills.
    """

    def emit(self, record: LogRecord) -> None:
        """Emit a log record and flush immediately.

        Overrides FileHandler.emit to ensure each log entry is immediately
        written to disk by flushing the file handle after writing.

        On Windows, also calls os.fsync() to force the OS to write buffered
        data to disk, ensuring the data is immediately available for reading.
        """
        super().emit(record)
        # Flush immediately after each log entry to ensure data is on disk
        self.flush()
        # Force OS to sync data to disk (critical on Windows for immediate reads)
        try:
            if self.stream and hasattr(self.stream, "fileno"):
                os.fsync(self.stream.fileno())
        except (OSError, AttributeError):
            # Ignore errors if fsync is not supported or file is closed
            pass


def get_step_logger(step_instance, logfile_name: str) -> Logger:
    """Configure and return a logger that writes to a step's logfile.

    This utility centralizes the logging setup logic for StepModel transactions,
    ensuring consistent log file handling across all steps.

    The logger uses FlushingFileHandler to ensure log entries are immediately
    written to disk, making them available for real-time monitoring and testing.
    """
    logger = getLogger(f"{step_instance.__class__.__module__}.{step_instance.__class__.__name__}")
    logger.setLevel(DEBUG)
    # Allow propagation so ansys root handlers (solution_logs fixture) see messages.
    logger.propagate = True

    # Get project directory from transaction context
    project_dir: Path | None = getattr(transaction_local, "project_directory", None)
    if project_dir is None:
        # Fallback: in-memory logging only (e.g., during testing)
        return logger

    # Set logfile path if not already set
    if step_instance.logfile is None:
        step_instance.logfile = str((project_dir / logfile_name).resolve())

    logfile_path = Path(step_instance.logfile).resolve()

    # Close and remove any FileHandlers that point to a different file. Leaving
    # them attached keeps the file handles open across tests (particularly on
    # Windows), which prevents temporary project directories from being deleted.
    handlers_to_keep: list[Handler] = []
    handlers_to_close: list[FileHandler] = []

    for handler in logger.handlers:
        if isinstance(handler, FileHandler):
            try:
                handler_path = Path(handler.baseFilename).resolve()
            except (OSError, ValueError):
                # If resolve() fails (e.g., handler already closed), fall back to raw path
                handler_path = Path(handler.baseFilename)

            if handler_path == logfile_path:
                handlers_to_keep.append(handler)
            else:
                handlers_to_close.append(handler)
        else:
            handlers_to_keep.append(handler)

    for handler in handlers_to_close:
        try:
            handler.flush()
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            handler.close()
        except (OSError, ValueError, RuntimeError):
            pass
        try:
            logger.removeHandler(handler)
        except (ValueError, RuntimeError):
            pass

    logger.handlers = handlers_to_keep

    def _resolved_base(h: FileHandler) -> Path | None:
        try:
            return Path(h.baseFilename).resolve()
        except (OSError, ValueError, TypeError):
            return None

    if not any(isinstance(h, FileHandler) and _resolved_base(h) == logfile_path for h in logger.handlers):
        # Use FlushingFileHandler to ensure immediate writes to disk
        file_handler = FlushingFileHandler(step_instance.logfile)
        formatter = Formatter(LOG_FORMAT)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
