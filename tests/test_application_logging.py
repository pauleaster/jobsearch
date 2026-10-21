from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper_module.application_logging import (
    build_log_path,
    format_log_filename,
    run_with_application_logging,
)


class ApplicationLoggingTests(unittest.TestCase):
    def test_build_log_filename_uses_timestamped_scraper_pattern(self):
        timestamp = "2026-10-03_12-34-56"

        self.assertEqual(
            format_log_filename(timestamp), "scraper_2026-10-03_12-34-56.log"
        )
        self.assertEqual(
            build_log_path(Path("C:/Users/paulj/logs/jobsearch"), timestamp),
            Path("C:/Users/paulj/logs/jobsearch/scraper_2026-10-03_12-34-56.log"),
        )

    def test_run_with_application_logging_creates_directory_and_tees_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs" / "jobsearch"
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            def work() -> None:
                print("stdout line")
                print("stderr line", file=sys.stderr)

            with (
                mock.patch.object(sys, "stdout", stdout_buffer),
                mock.patch.object(sys, "stderr", stderr_buffer),
            ):
                exit_code = run_with_application_logging(
                    log_dir,
                    work,
                    timestamp="2026-10-03_12-34-56",
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(log_dir.is_dir())

            log_path = log_dir / "scraper_2026-10-03_12-34-56.log"
            contents = log_path.read_text(encoding="utf-8")

            self.assertIn("Script started: 2026-10-03_12-34-56", contents)
            self.assertIn("stdout line", contents)
            self.assertIn("stderr line", contents)
            self.assertIn("Script ended:", contents)
            self.assertIn("stdout line", stdout_buffer.getvalue())
            self.assertIn("stderr line", stderr_buffer.getvalue())

    def test_run_with_application_logging_captures_traceback_to_log_and_stderr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs" / "jobsearch"
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            def work() -> None:
                print("before failure")
                print("problem on stderr", file=sys.stderr)
                raise ValueError("boom")

            with (
                mock.patch.object(sys, "stdout", stdout_buffer),
                mock.patch.object(sys, "stderr", stderr_buffer),
            ):
                exit_code = run_with_application_logging(
                    log_dir,
                    work,
                    timestamp="2026-10-03_12-34-56",
                )

            self.assertEqual(exit_code, 1)

            log_path = log_dir / "scraper_2026-10-03_12-34-56.log"
            contents = log_path.read_text(encoding="utf-8")

            self.assertIn("before failure", contents)
            self.assertIn("problem on stderr", contents)
            self.assertIn("Traceback (most recent call last):", contents)
            self.assertIn("ValueError: boom", contents)
            self.assertIn("before failure", stdout_buffer.getvalue())
            self.assertIn("problem on stderr", stderr_buffer.getvalue())
            self.assertIn(
                "Traceback (most recent call last):", stderr_buffer.getvalue()
            )


if __name__ == "__main__":
    unittest.main()
