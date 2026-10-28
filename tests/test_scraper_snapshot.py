from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scraper_module.scraper import JobScraper
from scraper_module.snapshot import (
    HTML_SNAPSHOT_TERMS,
    ScraperSnapshotManager,
    serialize_search_terms,
)


class FakeSoup:
    def __init__(self, html: str = "<html><body>job</body></html>"):
        self._html = html

    def __str__(self) -> str:
        return self._html

    def find(self, *_args, **_kwargs):
        return None


class FakeSession:
    def __init__(self):
        self.jobs: dict[str, SimpleNamespace] = {}
        self.execute_calls = 0

    def execute(self, _query):
        self.execute_calls += 1
        return None

    def query(self, *_entities):
        return FakeQuery(self)


class FakeQuery:
    def __init__(self, session: FakeSession):
        self.session = session
        self.filters: dict[str, object] = {}

    def filter_by(self, **kwargs):
        self.filters.update(kwargs)
        return self

    def join(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        job_number = self.filters.get("job_number")
        if job_number is None:
            return None
        return self.session.jobs.get(str(job_number))

    def all(self):
        return []


class FakeJobData:
    def __init__(self):
        self.session = FakeSession()
        self.seen_terms: dict[str, dict[str, bool]] = {}
        self.add_calls: list[tuple] = []
        self.closed = False

    def extract_job_number_from_url(self, url):
        return url.rsplit("/", 1)[-1]

    def get_search_terms_and_validities(self, job_number):
        return self.seen_terms.get(job_number, {})

    def calculate_job_date(self, job_age):
        return f"age-{job_age}"

    def add_or_update_link(
        self,
        search_term,
        url,
        job_number,
        job_date,
        status,
        salary=None,
        position=None,
        advertiser=None,
        location=None,
        work_type=None,
    ):
        self.add_calls.append(
            (
                search_term,
                url,
                job_number,
                job_date,
                status,
                salary,
                position,
                advertiser,
                location,
                work_type,
            )
        )
        self.session.jobs[str(job_number)] = SimpleNamespace(
            job_number=job_number,
            job_url=url,
            title="stored-title",
            comments=None,
            requirements=None,
            follow_up=None,
            highlight=None,
            applied=None,
            contact=None,
            application_comments=None,
            job_date=job_date,
            salary=salary,
            position=position,
            advertiser=advertiser,
            location=location,
            work_type=work_type,
            expired=False,
            updated_at=None,
        )
        self.seen_terms.setdefault(job_number, {})[search_term] = status.name == "VALID"

    def set_not_expired(self, _job_number):
        return None

    def close(self):
        self.closed = True


class FakeNetworkHandler:
    def __init__(self):
        self.search_base = "https://example.com/search"
        self.page_param_sep = "?"
        self.driver = SimpleNamespace(get=lambda _url: None)
        self.closed = False
        self.bytes_fetched = 0

    def initiate_search(self, _search_term):
        return None

    def handle_successive_url_read_delay(self):
        return None

    def selenium_interaction_delay(self):
        return None

    def get_current_page_soup(self):
        return FakeSoup()

    def extract_job_count(self, _soup):
        return 1

    def has_results(self, _soup):
        return False

    def close(self):
        self.closed = True


class ScraperSnapshotManagerTests(unittest.TestCase):
    def test_snapshot_directory_is_created_and_reused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ScraperSnapshotManager(
                snapshot_root=str(root / "job_metadata"),
                state_path=str(root / "scraper_state.csv"),
            )

            snapshot_id = manager.ensure_snapshot()
            assert snapshot_id is not None

            self.assertRegex(snapshot_id, r"^\d{8}T\d{6}Z$")
            self.assertTrue((root / "job_metadata" / snapshot_id).is_dir())
            self.assertEqual(manager.ensure_snapshot(snapshot_id), snapshot_id)

    def test_state_round_trips_with_snapshot_id_and_clear_truncates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ScraperSnapshotManager(
                snapshot_root=str(root / "job_metadata"),
                state_path=str(root / "scraper_state.csv"),
            )

            manager.save_state("python", 1, 3)
            loaded = manager.load_state()

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["search_term"], "python")
            self.assertEqual(loaded["url_index"], 1)
            self.assertEqual(loaded["page_number"], 3)
            self.assertEqual(loaded["snapshot_id"], manager.snapshot_id)

            manager.clear_state()
            self.assertEqual(
                (root / "scraper_state.csv").read_text(encoding="utf-8"), ""
            )

    def test_load_state_rejects_non_empty_state_without_snapshot_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "scraper_state.csv"
            state_path.write_text("python,1,3\n", encoding="utf-8")
            manager = ScraperSnapshotManager(
                snapshot_root=str(root / "job_metadata"),
                state_path=str(state_path),
            )

            with self.assertRaises(ValueError):
                manager.load_state()

    def test_load_state_rejects_malformed_non_empty_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "scraper_state.csv"
            state_path.write_text("not-a-valid-state\n", encoding="utf-8")
            manager = ScraperSnapshotManager(
                snapshot_root=str(root / "job_metadata"),
                state_path=str(state_path),
            )

            with self.assertRaises(ValueError):
                manager.load_state()

    def test_write_job_snapshot_creates_html_and_upserts_csv_by_job_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = ScraperSnapshotManager(
                snapshot_root=str(root / "job_metadata"),
                state_path=str(root / "scraper_state.csv"),
            )
            manager.ensure_snapshot("20260810T074730Z")

            row_one = {
                "job_number": "123456",
                "job_url": "https://example.com/job/123456",
                "title": "Initial title",
                "search_terms": "python",
            }
            manager.write_job_snapshot("123456", FakeSoup("<html>one</html>"), row_one)

            row_two = {
                "job_number": "123456",
                "job_url": "https://example.com/job/123456",
                "title": "Updated title",
                "search_terms": "python | fastapi",
            }
            manager.write_job_snapshot("123456", FakeSoup("<html>two</html>"), row_two)

            snapshot_dir = root / "job_metadata" / "20260810T074730Z"
            self.assertEqual(
                (snapshot_dir / "123456.html").read_text(encoding="utf-8"),
                "<html>one</html>",
            )

            with (snapshot_dir / "combined_job_search_results.csv").open(
                encoding="utf-8", newline=""
            ) as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["job_number"], "123456")
            self.assertEqual(rows[0]["title"], "Updated title")
            self.assertEqual(rows[0]["search_terms"], "python | fastapi")


class JobScraperSnapshotTests(unittest.TestCase):
    def _build_scraper(self, temp_root: Path) -> JobScraper:
        created_job_data: list[FakeJobData] = []

        def create_fake_job_data():
            job_data = FakeJobData()
            created_job_data.append(job_data)
            return job_data

        with (
            mock.patch(
                "scraper_module.scraper.JobData", side_effect=create_fake_job_data
            ),
            mock.patch("scraper_module.scraper.print"),
            mock.patch("scraper_module.database.engine.connect") as connect_mock,
        ):
            scraper = JobScraper(
                load_network_handler=False,
                snapshot_root=str(temp_root / "job_metadata"),
                state_path=str(temp_root / "scraper_state.csv"),
            )
            connect_mock.assert_not_called()
        scraper._test_created_job_data = created_job_data  # type: ignore[attr-defined]
        scraper.network_handlers = [FakeNetworkHandler() for _ in scraper.urls]
        return scraper

    def test_scraper_construction_does_not_touch_real_engine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)
            created_job_data = scraper.__dict__["_test_created_job_data"]

            self.assertIsInstance(scraper.job_data, FakeJobData)
            self.assertEqual(len(created_job_data), 2)
            self.assertEqual(created_job_data[0].session.execute_calls, 1)
            self.assertEqual(created_job_data[1].session.execute_calls, 0)

    def test_fetch_stats_report_total_results_not_page_job_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scraper = self._build_scraper(Path(temp_dir))

            with mock.patch("builtins.print") as print_mock:
                scraper._print_fetch_stats(
                    "platform engineer",
                    "https://example.com/in-All-Melbourne-VIC",
                    1,
                    663,
                )

            output = print_mock.call_args.args[0]
            self.assertIn("total matching results: 663", output)
            self.assertNotIn("jobs on page", output)
            self.assertEqual(print_mock.call_count, 1)

    def test_process_link_url_snapshots_only_for_qualifying_terms(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scraper = self._build_scraper(Path(temp_dir))
            with (
                mock.patch.object(
                    scraper,
                    "is_valid_link",
                    side_effect=[
                        (False, 2, False, FakeSoup()),
                        (True, 2, False, FakeSoup()),
                        (True, 2, False, FakeSoup()),
                    ],
                ),
                mock.patch.object(scraper, "_persist_job_snapshot") as persist_mock,
            ):
                scraper.process_link_url("https://example.com/job/123456", "python", 0)
                scraper.process_link_url(
                    "https://example.com/job/123457", "javascript", 0
                )
                scraper.process_link_url("https://example.com/job/123458", "python", 0)

            self.assertEqual(persist_mock.call_count, 1)
            self.assertEqual(len(scraper.job_data.add_calls), 3)

    def test_existing_dedupe_behavior_skips_same_search_term(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scraper = self._build_scraper(Path(temp_dir))
            scraper.job_data.seen_terms["123456"] = {"python": True}

            with (
                mock.patch.object(scraper, "_persist_job_snapshot") as persist_mock,
                mock.patch.object(
                    scraper,
                    "is_valid_link",
                    return_value=(True, 2, False, FakeSoup()),
                ),
            ):
                result = scraper.process_link_url(
                    "https://example.com/job/123456", "python", 0
                )

            self.assertFalse(result)
            persist_mock.assert_not_called()
            self.assertEqual(scraper.job_data.add_calls, [])

    def test_same_job_seen_first_under_non_snapshot_term_is_later_snapshotted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            scraper = self._build_scraper(Path(temp_dir))

            with (
                mock.patch.object(scraper, "_persist_job_snapshot") as persist_mock,
                mock.patch.object(
                    scraper,
                    "is_valid_link",
                    return_value=(True, 2, False, FakeSoup()),
                ),
            ):
                scraper.process_link_url(
                    "https://example.com/job/123456", "javascript", 0
                )
                scraper.process_link_url("https://example.com/job/123456", "python", 0)

            self.assertEqual(persist_mock.call_count, 1)

    def test_interrupted_run_preserves_partial_snapshot_and_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)

            def process_page_side_effect(*_args, **_kwargs):
                row = {
                    "job_number": "123456",
                    "job_url": "https://example.com/job/123456",
                    "title": "Partial title",
                    "search_terms": "python",
                }
                scraper.snapshot_manager.write_job_snapshot(
                    "123456",
                    FakeSoup("<html>partial</html>"),
                    row,
                )
                raise KeyboardInterrupt

            scraper.network_handlers = [FakeNetworkHandler() for _ in scraper.urls]

            with mock.patch.object(
                scraper, "process_page", side_effect=process_page_side_effect
            ):
                scraper.perform_searches(["python"])

            state_file = temp_root / "scraper_state.csv"
            snapshot_dir = next((temp_root / "job_metadata").iterdir())

            self.assertTrue(state_file.read_text(encoding="utf-8").strip())
            self.assertTrue((snapshot_dir / "123456.html").is_file())
            self.assertTrue(
                (snapshot_dir / "combined_job_search_results.csv").is_file()
            )

    def test_snapshot_csv_failure_does_not_clear_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)
            scraper.urls = [scraper.urls[0]]
            scraper.network_handlers = [FakeNetworkHandler()]

            original_upsert = scraper.snapshot_manager.upsert_csv_row

            def failing_upsert(csv_path, row):
                if row["job_number"] == "123456":
                    raise OSError("simulated csv failure")
                return original_upsert(csv_path, row)

            def process_page_side_effect(*_args, **_kwargs):
                with mock.patch.object(
                    scraper.snapshot_manager,
                    "upsert_csv_row",
                    side_effect=failing_upsert,
                ):
                    row = {
                        "job_number": "123456",
                        "job_url": "https://example.com/job/123456",
                        "title": "Broken title",
                        "search_terms": "python",
                    }
                    scraper.snapshot_manager.write_job_snapshot(
                        "123456",
                        FakeSoup("<html>broken</html>"),
                        row,
                    )

            with (
                mock.patch.object(scraper, "clear_state") as clear_mock,
                mock.patch.object(
                    scraper, "process_page", side_effect=process_page_side_effect
                ),
            ):
                scraper.perform_searches(["python"])

            state_file = temp_root / "scraper_state.csv"

            self.assertTrue(state_file.is_file())

            loaded_state = scraper.load_state()
            self.assertIsNotNone(loaded_state)
            assert loaded_state is not None
            self.assertEqual(
                loaded_state["snapshot_id"], scraper.snapshot_manager.snapshot_id
            )
            self.assertEqual(loaded_state["search_term"], "python")
            self.assertEqual(loaded_state["url_index"], 0)
            self.assertEqual(loaded_state["page_number"], 1)
            clear_mock.assert_not_called()

            snapshot_id = scraper.snapshot_manager.snapshot_id
            self.assertIsNotNone(snapshot_id)
            assert snapshot_id is not None
            snapshot_dir = temp_root / "job_metadata" / snapshot_id
            self.assertFalse((snapshot_dir / "123456.html").exists())
            self.assertFalse(
                (snapshot_dir / "combined_job_search_results.csv").exists()
            )

    def test_resume_recovers_snapshot_artifacts_after_csv_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)

            first_scraper = self._build_scraper(temp_root)
            first_scraper.urls = [first_scraper.urls[0]]
            first_scraper.network_handlers = [FakeNetworkHandler()]

            job_url = "https://example.com/job/123456"

            def failing_upsert(csv_path, row):
                if row["job_number"] == "123456":
                    raise OSError("simulated csv failure")
                return original_upsert(csv_path, row)

            original_upsert = first_scraper.snapshot_manager.upsert_csv_row

            def first_run_process_page(*_args, **_kwargs):
                with (
                    mock.patch.object(
                        first_scraper,
                        "is_valid_link",
                        return_value=(True, 2, False, FakeSoup("<html>broken</html>")),
                    ),
                    mock.patch.object(
                        first_scraper.snapshot_manager,
                        "upsert_csv_row",
                        side_effect=failing_upsert,
                    ),
                ):
                    return first_scraper.process_link_url(job_url, "python", 0)

            with mock.patch.object(
                first_scraper, "process_page", side_effect=first_run_process_page
            ):
                first_scraper.perform_searches(["python"])

            snapshot_id = first_scraper.snapshot_manager.snapshot_id
            self.assertIsNotNone(snapshot_id)
            assert snapshot_id is not None

            state_file = temp_root / "scraper_state.csv"
            self.assertTrue(state_file.is_file())

            resume_scraper = self._build_scraper(temp_root)
            resume_scraper.urls = [resume_scraper.urls[0]]
            resume_scraper.network_handlers = [FakeNetworkHandler()]
            resume_scraper.job_data = first_scraper.job_data

            def resume_process_page(*_args, **_kwargs):
                return resume_scraper.process_link_url(job_url, "python", 0)

            with (
                mock.patch.object(
                    resume_scraper,
                    "is_valid_link",
                    return_value=(True, 2, False, FakeSoup("<html>recovered</html>")),
                ),
                mock.patch.object(
                    resume_scraper, "process_page", side_effect=resume_process_page
                ),
            ):
                resume_scraper.perform_searches(["python"])

            self.assertEqual(resume_scraper.snapshot_manager.snapshot_id, snapshot_id)

            snapshot_dir = temp_root / "job_metadata" / snapshot_id
            self.assertTrue((snapshot_dir / "123456.html").exists())

            with (snapshot_dir / "combined_job_search_results.csv").open(
                encoding="utf-8", newline=""
            ) as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["job_number"], "123456")

    def test_snapshot_csv_failure_rolls_back_new_html(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)

            def failing_upsert(csv_path, row):
                raise OSError("simulated csv failure")

            with (
                mock.patch.object(
                    scraper.snapshot_manager,
                    "upsert_csv_row",
                    side_effect=failing_upsert,
                ),
                mock.patch.object(
                    scraper,
                    "is_valid_link",
                    return_value=(True, 2, False, FakeSoup()),
                ),
            ):
                with self.assertRaises(OSError):
                    scraper.process_link_url(
                        "https://example.com/job/123456", "python", 0
                    )

            snapshot_id = scraper.snapshot_manager.snapshot_id
            assert snapshot_id is not None
            snapshot_dir = temp_root / "job_metadata" / snapshot_id
            self.assertFalse((snapshot_dir / "123456.html").exists())
            self.assertFalse(
                (snapshot_dir / "combined_job_search_results.csv").exists()
            )

    def test_successful_page_processing_advances_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)
            scraper.urls = [scraper.urls[0]]
            scraper.network_handlers = [FakeNetworkHandler()]

            def process_page_side_effect(*_args, **_kwargs):
                row = {
                    "job_number": "123456",
                    "job_url": "https://example.com/job/123456",
                    "title": "Complete title",
                    "search_terms": "python",
                }
                scraper.snapshot_manager.write_job_snapshot(
                    "123456",
                    FakeSoup("<html>complete</html>"),
                    row,
                )
                return False

            with (
                mock.patch.object(scraper, "clear_state") as clear_mock,
                mock.patch.object(
                    scraper, "process_page", side_effect=process_page_side_effect
                ),
            ):
                scraper.perform_searches(["python"])

            state_file = temp_root / "scraper_state.csv"
            self.assertTrue(state_file.is_file())
            self.assertIn("python", state_file.read_text(encoding="utf-8"))
            clear_mock.assert_called_once()

    def test_snapshot_failure_does_not_advance_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)
            scraper.urls = [scraper.urls[0]]
            scraper.network_handlers = [FakeNetworkHandler()]

            def process_page_side_effect(*_args, **_kwargs):
                with mock.patch.object(
                    scraper.snapshot_manager,
                    "upsert_csv_row",
                    side_effect=OSError("simulated csv failure"),
                ):
                    row = {
                        "job_number": "123456",
                        "job_url": "https://example.com/job/123456",
                        "title": "Broken title",
                        "search_terms": "python",
                    }
                    scraper.snapshot_manager.write_job_snapshot(
                        "123456",
                        FakeSoup("<html>broken</html>"),
                        row,
                    )

            with (
                mock.patch.object(scraper, "clear_state") as clear_mock,
                mock.patch.object(
                    scraper, "process_page", side_effect=process_page_side_effect
                ),
            ):
                scraper.perform_searches(["python"])

            state_file = temp_root / "scraper_state.csv"
            self.assertTrue(state_file.is_file())

            loaded_state = scraper.load_state()
            self.assertIsNotNone(loaded_state)
            assert loaded_state is not None
            self.assertEqual(
                loaded_state["snapshot_id"], scraper.snapshot_manager.snapshot_id
            )
            self.assertEqual(loaded_state["search_term"], "python")
            self.assertEqual(loaded_state["url_index"], 0)
            self.assertEqual(loaded_state["page_number"], 1)
            clear_mock.assert_not_called()

            snapshot_id = scraper.snapshot_manager.snapshot_id
            self.assertIsNotNone(snapshot_id)
            assert snapshot_id is not None
            snapshot_dir = temp_root / "job_metadata" / snapshot_id
            self.assertFalse((snapshot_dir / "123456.html").exists())
            self.assertFalse(
                (snapshot_dir / "combined_job_search_results.csv").exists()
            )

    def test_successful_completion_clears_state_after_snapshot_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            scraper = self._build_scraper(temp_root)

            def process_page_side_effect(*_args, **_kwargs):
                row = {
                    "job_number": "123456",
                    "job_url": "https://example.com/job/123456",
                    "title": "Complete title",
                    "search_terms": "python",
                }
                scraper.snapshot_manager.write_job_snapshot(
                    "123456",
                    FakeSoup("<html>complete</html>"),
                    row,
                )
                return False

            scraper.network_handlers = [FakeNetworkHandler() for _ in scraper.urls]

            with mock.patch.object(
                scraper, "process_page", side_effect=process_page_side_effect
            ):
                scraper.perform_searches(["python"])

            state_file = temp_root / "scraper_state.csv"
            snapshot_dir = next((temp_root / "job_metadata").iterdir())

            self.assertEqual(state_file.read_text(encoding="utf-8"), "")
            self.assertTrue((snapshot_dir / "123456.html").is_file())
            self.assertTrue(
                (snapshot_dir / "combined_job_search_results.csv").is_file()
            )


class SearchTermSerializationTests(unittest.TestCase):
    def test_serialize_search_terms_uses_pipe_delimited_format(self):
        self.assertEqual(
            serialize_search_terms(["term1", "term2", "term3"]), "term1 | term2 | term3"
        )

    def test_html_snapshot_term_policy_is_present(self):
        self.assertIn("python", HTML_SNAPSHOT_TERMS)
        self.assertIn("docker", HTML_SNAPSHOT_TERMS)


if __name__ == "__main__":
    unittest.main()
