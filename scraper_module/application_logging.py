from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
LOG_FILENAME_PREFIX = "scraper_"


def format_log_filename(timestamp: str) -> str:
    return f"{LOG_FILENAME_PREFIX}{timestamp}.log"


def build_log_path(log_dir: str | Path, timestamp: str) -> Path:
    return Path(log_dir) / format_log_filename(timestamp)


def current_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


class TeeTextStream:
    def __init__(self, original_stream, log_stream):
        self._original_stream = original_stream
        self._log_stream = log_stream

    def write(self, text: str) -> int:
        self._original_stream.write(text)
        self._log_stream.write(text)
        self.flush()
        return len(text)

    def flush(self) -> None:
        self._original_stream.flush()
        self._log_stream.flush()

    @property
    def encoding(self):
        return getattr(self._original_stream, "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._original_stream, "errors", "strict")

    @property
    def newlines(self):
        return getattr(self._original_stream, "newlines", None)

    def isatty(self) -> bool:
        return bool(getattr(self._original_stream, "isatty", lambda: False)())


@dataclass
class ApplicationLogSession:
    log_dir: Path
    timestamp: str | None = None

    def __post_init__(self) -> None:
        self.log_dir = Path(self.log_dir)
        self.timestamp = self.timestamp or current_timestamp()
        self.log_path = build_log_path(self.log_dir, self.timestamp)
        self._log_file = None
        self._original_stdout = None
        self._original_stderr = None

    def start(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_path.open("w", encoding="utf-8")
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = TeeTextStream(self._original_stdout, self._log_file)
        sys.stderr = TeeTextStream(self._original_stderr, self._log_file)
        print(f"Script started: {self.timestamp}", flush=True)

    def finish(self) -> None:
        print(f"Script ended: {current_timestamp()}", flush=True)
        if self._log_file is not None:
            self._log_file.flush()
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
        if self._original_stderr is not None:
            sys.stderr = self._original_stderr
        if self._log_file is not None:
            self._log_file.close()


def run_with_application_logging(
    log_dir: str | Path,
    work: Callable[[], None],
    timestamp: str | None = None,
) -> int:
    session = ApplicationLogSession(Path(log_dir), timestamp=timestamp)
    session.start()
    exit_code = 0
    try:
        work()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        exit_code = 1
    finally:
        session.finish()
    return exit_code
