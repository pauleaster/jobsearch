from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import create_job_metadata as job_metadata_script


class FakeSoup:
    def __init__(self, html: str):
        self._html = html

    def __str__(self) -> str:
        return self._html


class FakeNetworkHandler:
    def __init__(self, url: str):
        self.url = url
        self.closed = False
        self.delay_calls = 0

    def handle_successive_url_read_delay(self):
        self.delay_calls += 1

    def get_soup(self, url: str):
        job_number = url.rsplit("/", 1)[-1]
        return FakeSoup(f"<html><body>{job_number}</body></html>")

    def close(self):
        self.closed = True


class CreateJobMetadataTests(unittest.TestCase):
    def test_find_latest_snapshot_dir_prefers_most_recent_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir)
            older = runs_root / "20260810T064730Z"
            newer = runs_root / "20260810T074730Z"
            ignored = runs_root / "not-a-snapshot"
            older.mkdir()
            newer.mkdir()
            ignored.mkdir()

            latest = job_metadata_script.find_latest_snapshot_dir(runs_root)

            self.assertEqual(latest, newer)

    def test_main_uses_latest_snapshot_and_writes_run_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo_root = temp_root / "jobsearch"
            backend_root = temp_root / "backend" / "runs"
            latest_snapshot = backend_root / "20260810T074730Z"
            older_snapshot = backend_root / "20260810T064730Z"
            repo_root.mkdir()
            latest_snapshot.mkdir(parents=True)
            older_snapshot.mkdir(parents=True)

            latest_csv = latest_snapshot / "combined_job_search_results.csv"
            older_csv = older_snapshot / "combined_job_search_results.csv"

            with latest_csv.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["job_url", "job_number"])
                writer.writeheader()
                writer.writerow({"job_url": "https://example.com/job/123456", "job_number": "123456"})
                writer.writerow({"job_url": "https://example.com/job/123457", "job_number": "123457"})

            with older_csv.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["job_url", "job_number"])
                writer.writeheader()
                writer.writerow({"job_url": "https://example.com/job/999999", "job_number": "999999"})

            older_html = older_snapshot / "preserved.html"
            older_html.write_text("keep me", encoding="utf-8")

            with mock.patch.object(job_metadata_script, "REPO_ROOT", repo_root), mock.patch.object(
                job_metadata_script, "BACKEND_RUNS_ROOT", backend_root
            ), mock.patch.object(job_metadata_script, "NetworkHandler", FakeNetworkHandler):
                job_metadata_script.main()

            output_dir = repo_root / "job_metadata" / "20260810T074730Z"
            copied_csv = output_dir / "combined_job_search_results.csv"

            self.assertTrue(output_dir.is_dir())
            self.assertTrue(copied_csv.is_file())
            self.assertEqual((output_dir / "123456.html").read_text(encoding="utf-8"), "<html><body>123456</body></html>")
            self.assertEqual((output_dir / "123457.html").read_text(encoding="utf-8"), "<html><body>123457</body></html>")
            self.assertEqual(older_html.read_text(encoding="utf-8"), "keep me")
            self.assertFalse((older_snapshot / "999999.html").exists())

    def test_main_refuses_to_overwrite_existing_snapshot_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            repo_root = temp_root / "jobsearch"
            backend_root = temp_root / "backend" / "runs"
            snapshot_dir = backend_root / "20260810T074730Z"
            repo_output_dir = repo_root / "job_metadata" / "20260810T074730Z"
            repo_root.mkdir()
            snapshot_dir.mkdir(parents=True)
            repo_output_dir.mkdir(parents=True)

            csv_path = snapshot_dir / "combined_job_search_results.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["job_url", "job_number"])
                writer.writeheader()
                writer.writerow({"job_url": "https://example.com/job/123456", "job_number": "123456"})

            with mock.patch.object(job_metadata_script, "REPO_ROOT", repo_root), mock.patch.object(
                job_metadata_script, "BACKEND_RUNS_ROOT", backend_root
            ), mock.patch.object(job_metadata_script, "NetworkHandler", FakeNetworkHandler):
                with self.assertRaises(FileExistsError):
                    job_metadata_script.main()


if __name__ == "__main__":
    unittest.main()