import unittest
from types import SimpleNamespace
from unittest import mock

from bs4 import BeautifulSoup

import scraper_module.handlers as handlers_module
from scraper_module.handlers import NetworkHandler


class NetworkHandlerTests(unittest.TestCase):
    def test_extract_job_count_from_melbourne_job_counter(self):
        soup = BeautifulSoup(
            '<span data-automation="jobCounter">663 jobs</span>', "html.parser"
        )

        self.assertEqual(NetworkHandler.extract_job_count(None, soup), 663)

    def test_extract_job_count_accepts_duplicate_identical_counters(self):
        soup = BeautifulSoup(
            """
            <span data-automation="jobCounter">663 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            """,
            "html.parser",
        )

        self.assertEqual(NetworkHandler.extract_job_count(None, soup), 663)

    def test_extract_job_count_from_remote_filtered_results(self):
        soup = BeautifulSoup(
            '<span data-automation="jobCounter">17 jobs</span>', "html.parser"
        )

        self.assertEqual(NetworkHandler.extract_job_count(None, soup), 17)

    def test_extract_job_count_returns_none_for_conflicting_counters(self):
        soup = BeautifulSoup(
            """
            <span data-automation="jobCounter">17 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            <span data-automation="jobCounter">663 jobs</span>
            """,
            "html.parser",
        )

        self.assertIsNone(NetworkHandler.extract_job_count(None, soup))

    def test_extract_job_count_uses_legacy_selector_as_fallback(self):
        soup = BeautifulSoup(
            """
            <div data-automation="totalJobsMessage">
                17 jobs nearby <span>663 jobs</span>
            </div>
            """,
            "html.parser",
        )

        self.assertEqual(NetworkHandler.extract_job_count(None, soup), 663)

    def test_extract_job_count_returns_none_when_missing(self):
        self.assertIsNone(
            NetworkHandler.extract_job_count(
                None, BeautifulSoup("<html><body>No count</body></html>", "html.parser")
            )
        )

    def _handler_for_response(self, html=None, exception=None):
        driver = SimpleNamespace(
            get=mock.Mock(side_effect=exception),
            page_source=html,
        )
        handler = NetworkHandler.__new__(NetworkHandler)
        handler.driver = driver
        handler.bytes_fetched = 0
        handler.handle_successive_url_read_delay = mock.Mock()
        handler.selenium_interaction_delay = mock.Mock()
        handler.is_cloudflare_challenge_page = mock.Mock(return_value=False)
        handler._apply_delay_variance = lambda delay: delay
        return handler

    def _run_retries(self, html, max_retries=5, exception=None):
        handler = self._handler_for_response(html=html, exception=exception)
        with (
            mock.patch.object(handlers_module.time, "sleep") as sleep_mock,
            mock.patch("builtins.print") as print_mock,
        ):
            result = handler.get_soup(
                "https://example.test/job/1",
                max_retries=max_retries,
                base_delay=60,
            )
        return handler, result, sleep_mock, print_mock

    def test_five_503_attempts_have_four_backoffs_and_distinct_diagnostics(self):
        html = "<html><head><title>Technical error</title></head></html>"

        handler, result, sleep_mock, print_mock = self._run_retries(html)

        self.assertIsNone(result)
        self.assertEqual(handler.driver.get.call_count, 5)
        self.assertEqual(
            [call.args[0] for call in sleep_mock.call_args_list], [60, 120, 240, 480]
        )
        output = " ".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("503 technical error page detected", output)
        self.assertNotIn("429 rate-limit page detected", output)
        self.assertEqual(output.count("Retrying after detected error page"), 4)

    def test_five_429_attempts_have_four_backoffs_and_distinct_diagnostics(self):
        html = "<html><body>Too many requests</body></html>"

        handler, result, sleep_mock, print_mock = self._run_retries(html)

        self.assertIsNone(result)
        self.assertEqual(handler.driver.get.call_count, 5)
        self.assertEqual(
            [call.args[0] for call in sleep_mock.call_args_list], [60, 120, 240, 480]
        )
        output = " ".join(str(call.args[0]) for call in print_mock.call_args_list)
        self.assertIn("429 rate-limit page detected", output)
        self.assertNotIn("503 technical error page detected", output)
        self.assertEqual(output.count("Retrying after detected error page"), 4)

    def test_five_exceptions_have_four_backoffs(self):
        handler, result, sleep_mock, _ = self._run_retries(
            html=None, exception=RuntimeError("network failure")
        )

        self.assertIsNone(result)
        self.assertEqual(handler.driver.get.call_count, 5)
        self.assertEqual(
            [call.args[0] for call in sleep_mock.call_args_list], [60, 120, 240, 480]
        )

    def test_single_attempt_does_not_back_off(self):
        html = "<html><body>Too many requests</body></html>"

        handler, result, sleep_mock, print_mock = self._run_retries(html, max_retries=1)

        self.assertIsNone(result)
        self.assertEqual(handler.driver.get.call_count, 1)
        sleep_mock.assert_not_called()
        self.assertFalse(
            any(
                "Retrying after" in str(call.args) for call in print_mock.call_args_list
            )
        )

    def test_final_cloudflare_attempt_does_not_recover_for_another_attempt(self):
        handler = self._handler_for_response(html="<html></html>")
        handler.is_cloudflare_challenge_page = mock.Mock(return_value=True)
        handler.recover_browser = mock.Mock()

        with (
            mock.patch.object(handlers_module.time, "sleep") as sleep_mock,
            mock.patch("builtins.print") as print_mock,
        ):
            result = handler.get_soup(
                "https://example.test/job/1", max_retries=1, base_delay=60
            )

        self.assertIsNone(result)
        self.assertEqual(handler.driver.get.call_count, 1)
        handler.recover_browser.assert_not_called()
        sleep_mock.assert_not_called()
        self.assertFalse(
            any(
                "retrying after" in str(call.args).lower()
                for call in print_mock.call_args_list
            )
        )

    def test_transient_error_then_success_retries_and_returns_soup(self):
        handler = self._handler_for_response()
        handler.driver.get = mock.Mock(
            side_effect=[
                None,
                None,
            ]
        )
        handler.driver.page_source = "<html><body>job details</body></html>"
        handler.is_429_page = mock.Mock(side_effect=[True, False])

        with mock.patch.object(handlers_module.time, "sleep") as sleep_mock:
            result = handler.get_soup(
                "https://example.test/job/1", max_retries=5, base_delay=60
            )

        self.assertIsNotNone(result)
        self.assertEqual(handler.driver.get.call_count, 2)
        sleep_mock.assert_called_once_with(60)
