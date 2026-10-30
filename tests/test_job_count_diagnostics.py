import unittest
from types import SimpleNamespace
from unittest import mock

from bs4 import BeautifulSoup

from scraper_module.handlers import NetworkHandler
from scraper_module.scraper import JobScraper


class JobCountDiagnosticTests(unittest.TestCase):
    def _handler(self):
        return SimpleNamespace(
            extract_job_count=lambda soup: NetworkHandler.extract_job_count(None, soup),
            get_job_count_failure_diagnostic=(
                NetworkHandler.get_job_count_failure_diagnostic
            ),
        )

    def _scraper(self):
        scraper = JobScraper.__new__(JobScraper)
        scraper.network_handlers = [self._handler()]
        scraper._logged_job_count_diagnostics = set()
        return scraper

    def test_missing_count_elements_are_diagnosed(self):
        soup = BeautifulSoup("<html><body>No count</body></html>", "html.parser")

        diagnostic = NetworkHandler.get_job_count_failure_diagnostic(soup)

        self.assertEqual(diagnostic["reason"], "no_matching_elements")
        self.assertTrue(diagnostic["soup_available"])
        self.assertEqual(diagnostic["job_counter_count"], 0)
        self.assertEqual(diagnostic["total_jobs_message_count"], 0)
        self.assertEqual(
            NetworkHandler.get_job_count_failure_diagnostic(None)["reason"],
            "missing_soup",
        )

    def test_conflicting_counter_values_are_reported(self):
        soup = BeautifulSoup(
            """
            <span data-automation="jobCounter">17 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            """,
            "html.parser",
        )

        diagnostic = NetworkHandler.get_job_count_failure_diagnostic(soup)

        self.assertEqual(diagnostic["reason"], "conflicting_counters")
        self.assertEqual(diagnostic["job_counter_count"], 3)
        self.assertEqual(diagnostic["job_counter_values"], [17, 663, 663])

    def test_unparseable_counter_is_identified_with_bounded_sample(self):
        text = "not a count " + ("x" * 100)
        soup = BeautifulSoup(
            f'<span data-automation="jobCounter">{text}</span>', "html.parser"
        )

        diagnostic = NetworkHandler.get_job_count_failure_diagnostic(soup)

        self.assertEqual(diagnostic["reason"], "unparseable_counter")
        self.assertEqual(diagnostic["job_counter_values"], [None])
        self.assertEqual(len(diagnostic["sample"]), 80)

    def test_unparseable_legacy_message_is_distinguished(self):
        soup = BeautifulSoup(
            """
            <div data-automation="totalJobsMessage">
                <span>results are loading</span>
            </div>
            """,
            "html.parser",
        )

        diagnostic = NetworkHandler.get_job_count_failure_diagnostic(soup)

        self.assertEqual(diagnostic["reason"], "unparseable_legacy_message")
        self.assertEqual(diagnostic["total_jobs_message_count"], 1)
        self.assertIsNone(diagnostic["legacy_value"])
        self.assertEqual(diagnostic["sample"], "results are loading")

    def test_successful_extraction_emits_no_failure_diagnostic(self):
        scraper = self._scraper()
        soup = BeautifulSoup(
            '<span data-automation="jobCounter">19 jobs</span>', "html.parser"
        )

        with mock.patch("builtins.print") as print_mock:
            result = scraper._extract_job_count(
                soup, "python", "https://example.test/in-Melbourne", 1, 0
            )

        self.assertEqual(result, 19)
        print_mock.assert_not_called()

    def test_unclassified_failure_is_logged_without_raising(self):
        scraper = self._scraper()
        scraper.network_handlers[0].get_job_count_failure_diagnostic = mock.Mock(
            return_value=None
        )
        soup = BeautifulSoup("<html><body>No count</body></html>", "html.parser")

        with mock.patch("builtins.print") as print_mock:
            result = scraper._extract_job_count(
                soup, "python", "https://example.test/in-Melbourne", 1, 0
            )

        self.assertIsNone(result)
        print_mock.assert_called_once()
        self.assertIn("reason=unclassified", print_mock.call_args.args[0])

    def test_repeated_failure_logs_once_for_same_reason_and_search(self):
        scraper = self._scraper()
        soup = BeautifulSoup("<html><body>No count</body></html>", "html.parser")

        with mock.patch("builtins.print") as print_mock:
            for page_number in (1, 2):
                result = scraper._extract_job_count(
                    soup,
                    "python",
                    "https://example.test/in-Melbourne",
                    page_number,
                    0,
                )
                self.assertIsNone(result)

        print_mock.assert_called_once()
        output = print_mock.call_args.args[0]
        self.assertIn("term='python'", output)
        self.assertIn("location='in-Melbourne'", output)
        self.assertIn("page=1", output)
        self.assertIn("reason=no_matching_elements", output)

    def test_different_reasons_are_each_logged_once(self):
        scraper = self._scraper()
        missing_elements = BeautifulSoup(
            "<html><body>No count</body></html>", "html.parser"
        )
        conflicting_counters = BeautifulSoup(
            """
            <span data-automation="jobCounter">17 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            """,
            "html.parser",
        )

        with mock.patch("builtins.print") as print_mock:
            for page_number, soup in (
                (1, missing_elements),
                (2, missing_elements),
                (3, conflicting_counters),
                (4, conflicting_counters),
            ):
                scraper._extract_job_count(
                    soup,
                    "python",
                    "https://example.test/in-Melbourne",
                    page_number,
                    0,
                )

        self.assertEqual(print_mock.call_count, 2)
        output = "\n".join(call.args[0] for call in print_mock.call_args_list)
        self.assertIn("reason=no_matching_elements", output)
        self.assertIn("reason=conflicting_counters", output)
        self.assertIn("values=[17, 663]", output)


if __name__ == "__main__":
    unittest.main()
