"""
handlers.py

This module defines structures and utilities for web access and page scraping:

- `NetworkHandler`: Manages web interactions using Selenium and requests, with
  appropriate delays set by `DelaySettings` to avoid request rate limits or bans.

Examples:
    >>> handler = NetworkHandler('https://url.for.job.search/jobs)
    >>> links = handler.find_job_links()
    >>> soup = handler.get_soup('https://url.for.job.search/job/123')

Note: Always handle web scraping responsibly, respecting robots.txt and website
policies.
"""

import time
import re
import random
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from bs4 import BeautifulSoup

from .delays import DelaySettings


class NetworkHandler:
    """
    Manages web access using Selenium for browser interactions and requests for
    HTTP requests, with delays set by `DelaySettings`.
    """

    def __init__(self, url):
        """
        Initialize a handler, set up the Selenium driver and open the URL.
        """
        self.successive_url_read_delay = DelaySettings.SUCCESSIVE_URL_READ_DELAY.value
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.bytes_fetched = 0
        self.cloudflare_retry_delay = DelaySettings.CLOUDFLARE_RETRY_DELAY.value
        self.driver = self._create_driver()
        self.wait = WebDriverWait(self.driver, self.successive_url_read_delay)
        print(f"Opening {url}")
        self.handle_successive_url_read_delay()
        self.driver.get(url) # Network access
        self.initial_url = url
        self._successive_url_delay_elapsed = 0

        


    @staticmethod
    def _create_driver():
        chrome_options = Options()
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        return webdriver.Chrome(options=chrome_options)


    def selenium_interaction_delay(self):
        """
        Delay for Selenium interactions to allow the browser to react.
        """
        time.sleep(self._apply_delay_variance(DelaySettings.SELENIUM_INTERACTION_DELAY.value))

    @staticmethod
    def _apply_delay_variance(delay_seconds):
        """
        Apply a positive variance factor to the provided delay.
        """
        variance_multiplier = 1 + random.uniform(0, DelaySettings.VARIANCE_FACTOR.value)
        return delay_seconds * variance_multiplier

    def find_elements(self, by, value):  # pylint: disable=invalid-name
        """
        Find and return web elements based on the provided criteria.
        """
        elements = self.driver.find_elements(by, value)
        self.selenium_interaction_delay()
        return elements

    def find_job_links(self):
        """
        Find and return job links on the current page.
        """
        self.get_current_page_soup()
        xpath_expression = '//a[contains(@href, "/job/")]'
        return self.find_elements(By.XPATH, xpath_expression)

    @staticmethod
    def format_search_term(search_term):
        """
        Format the search term for use in a job search URL.
        This method replaces spaces with hyphens and trims whitespace.
        Also replaces ++ with %2B%2B for C++ and # with %23 for C#.
        """
        return search_term.strip().replace(" ", "-").replace("++", "%2B%2B").replace("#", "%23")

    def extract_base_and_location(self):
        """
        Extract the base URL and location segment from the current URL.
        Returns (base_url, location).
        """
        url = self.initial_url.rstrip('/')
        parts = url.split('/')
        base_url = '/'.join(parts[:3])
        location = parts[-1]
        return base_url, location

    def initiate_search(self, search_term):
        """
        Initiate a search by constructing the URL based on the search term and current location,
        then navigating to it. For 'C++' or terms containing '/', uses keyword query params.
        """
        self.search_term = search_term
        base_url, location = self.extract_base_and_location()
        self.formatted_term = self.format_search_term(search_term)

        if search_term.strip().lower() == "c++":
            # Bring this window to front and request OS focus
            self.driver.switch_to.window(self.driver.current_window_handle)
            self.driver.execute_script("window.focus();")
            self.handle_successive_url_read_delay()
            self.driver.get(f"{base_url}/jobs/{location}")

            # Wait until the search input is present and interactable
            try:
                search_input = WebDriverWait(self.driver, 15).until(
                    EC.element_to_be_clickable((By.NAME, 'keywords'))
                )
            except TimeoutException:
                # Diagnostic snapshot on failure
                self.driver.save_screenshot("cpp_search_input_missing.png")
                print(f"DEBUG: URL = {self.driver.current_url}")
                print(f"DEBUG: title = {self.driver.title}")
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                print(f"DEBUG: inputs on page = {[e.get_attribute('placeholder') for e in inputs]}")
                raise

            search_input.clear()
            search_input.send_keys("C++")

            search_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "searchButton"))
            )
            search_button.click()
            self.selenium_interaction_delay()
            self.search_base = None
            self.page_param_sep = None
        elif "/" in search_term:
            # Terms like "ci/cd" must use the keyword query parameter URL
            encoded_term = search_term.strip().replace("/", "%2F").replace(" ", "+")
            search_url = f"{base_url}/jobs/{location}?keywords={encoded_term}"
            self.search_base = search_url
            self.page_param_sep = "&"
            print(f"Navigating to search URL: {search_url}")
            self.handle_successive_url_read_delay()
            self.driver.get(search_url)
            self.selenium_interaction_delay()
        else:
            search_url = f"{base_url}/{self.formatted_term}-jobs/{location}"
            self.search_base = search_url
            self.page_param_sep = "?"
            print(f"Navigating to search URL: {search_url}")
            self.handle_successive_url_read_delay()
            self.driver.get(search_url)
            self.selenium_interaction_delay()

    def click_next_button(self):
        """
        Click the next button on a page, if available.
        Returns True if successful, False otherwise.
        """
        try:
            next_button = self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//a[starts-with(@data-automation, "page-") and @aria-label="Next"]',
                    )
                )
            )
            time.sleep(
                self._apply_delay_variance(
                    DelaySettings.SCROLL_TO_NEXT_BUTTON_DELAY.value
                )
            )
            next_button.click()
            self.selenium_interaction_delay()
            return True  # Successfully clicked the button

        except (
            ElementClickInterceptedException,
            NoSuchElementException,
            TimeoutException,
        ) as exception:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(exception, ElementClickInterceptedException):
                print(f"[{timestamp}] Next button click intercepted.")
            elif isinstance(exception, NoSuchElementException):
                print(f"[{timestamp}] Next button not found.")
            elif isinstance(exception, TimeoutException):
                print(f"[{timestamp}] Timed out waiting for the Next button.")
            else:
                print(f"[{timestamp}] Failed to click the Next button: {exception}")
            return False

    def handle_successive_url_read_delay(self):
        """
        Implement a delay between successive URL reads based on `DelaySettings`.
        """
        successive_url_read_delay = self._apply_delay_variance(
            DelaySettings.SUCCESSIVE_URL_READ_DELAY.value
        )
        self.time_since_last_request = time.time() - self.last_request_time
        if self.time_since_last_request < successive_url_read_delay:
            time.sleep(successive_url_read_delay - self.time_since_last_request)
        self.last_request_time = time.time()

    def get_soup(self, url, max_retries=5, base_delay=60):
        """
        Use Selenium to fetch the page and return a BeautifulSoup object.
        Retries on 429-like rate limiting detected in the page content, with exponential backoff.
        """
        retries = 0
        delay = base_delay
        last_exception = None
        while retries < max_retries:
            try:
                self.handle_successive_url_read_delay()
                self.driver.get(url)
                self.selenium_interaction_delay()
                html = self.driver.page_source
                soup = BeautifulSoup(html, "html.parser")
                if self.is_cloudflare_challenge_page(soup):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] Cloudflare challenge page detected for URL: {url}")
                    self.recover_browser(url)
                    retries += 1
                    continue
                if self.is_429_page(soup, url):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{timestamp}] 429-like page detected, retrying after {delay} seconds...")
                    time.sleep(self._apply_delay_variance(delay))
                    delay *= 2  # Exponential backoff
                    retries += 1
                    continue
                self.bytes_fetched += len(html.encode("utf-8"))
                return soup
            except Exception as exception:
                print("E", end="")
                time.sleep(self._apply_delay_variance(delay))
                delay *= 2  # Exponential backoff
                retries += 1
                last_exception = exception
        print(f"Exceeded maximum retries for URL: {url}")
        if last_exception:
            print(f"Last exception: {last_exception}")
        return None

    def close(self):
        """
        Gracefully close the Selenium driver.
        """
        try:
            if getattr(self, "driver", None):
                print("Calling driver.quit()...", flush=True)
                self.driver.quit()
        except Exception as e:
            print(f"driver.quit() raised: {e!r}", flush=True)

    def recover_browser(self, url):
        """
        Close the current browser session, wait, and recreate it before retrying.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[{timestamp}] Cloudflare challenge detected for URL: {url}. Closing browser and retrying after {self.cloudflare_retry_delay} seconds..."
        )
        self.close()
        time.sleep(self._apply_delay_variance(self.cloudflare_retry_delay))
        self.driver = self._create_driver()
        self.wait = WebDriverWait(self.driver, self.successive_url_read_delay)
        self.driver.get(url)
        self.selenium_interaction_delay()

    def is_cloudflare_challenge_page(self, soup):
        """
        Detect Cloudflare verification pages that block normal scraping.
        """
        text = soup.get_text(separator=" ", strip=True).lower()
        title = soup.title.string.lower() if soup.title and soup.title.string else ""
        html = str(soup).lower()

        if "just a moment" in title:
            return True
        if "performing security verification" in text:
            return True
        if "verify you are a human" in text:
            return True
        if "verification successful" in text and "cloudflare" in text:
            return True
        if "challenges.cloudflare.com" in html:
            return True
        return False

    def is_429_page(self, soup, url=None):
        """
        Detect if the loaded page is a 429 Too Many Requests error page.
        Prints which trigger was found and the current URL, and context for '429'.
        """
        text = soup.get_text(separator=" ", strip=True).lower()
        if "too many requests" in text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f'[{timestamp}] "too many requests" found in page for URL: {url}')
            return True
        # Detect the site's 503 "Technical error" page
        title = soup.title.string.lower() if soup.title and soup.title.string else ""
        if "technical error" in title:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f'[{timestamp}] 503 technical error page detected for URL: {url}')
            return True
        if "can we try that again" in text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f'[{timestamp}] 503 technical error page detected (body text) for URL: {url}')
            return True
        return False

    def has_results(self, soup):
        """
        Returns True if the page has job results, False if 'No matching search results' is found.
        """
        if soup is None:
            return False
        text = soup.get_text(separator=" ", strip=True).lower().replace("\u2019", "'")
        if "no matching search results" in text:
            return False
        if "we couldn't find that page" in text:
            return False
        return True

    def extract_job_count(self, soup):
        """
        Extract the displayed total job count from the search results page.
        """
        if soup is None:
            return None
        total_jobs_message = soup.find(attrs={"data-automation": "totalJobsMessage"})
        if total_jobs_message is None:
            return None

        inner_span = total_jobs_message.find("span")
        text = (
            inner_span.get_text(separator=" ", strip=True)
            if inner_span is not None
            else total_jobs_message.get_text(separator=" ", strip=True)
        ).lower().replace("\u2019", "'")

        match = re.search(r"(\d[\d,]*)\s+jobs?\b", text)
        if match:
            return int(match.group(1).replace(",", ""))
        return None

    def get_current_page_soup(self):
        """
        Return a BeautifulSoup object for the current Selenium page source.
        """
        html = self.driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        if self.is_cloudflare_challenge_page(soup):
            self.recover_browser(self.driver.current_url)
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
        return soup

    def refresh(self):
        """
        Refresh the current page to keep the Selenium session alive.
        """
        try:
            self.driver.refresh()
            self.selenium_interaction_delay()
        except Exception as e:
            print(f"Refresh failed: {e}")

    @staticmethod
    def truncate_featured_jobs(soup):
        """
        Truncates the HTML at <h4 ...>Featured jobs</h4> and returns a new soup object
        containing only the content before this section.
        """
        html = str(soup)
        match = re.search(r"<h4[^>]*>\s*Featured jobs\s*</h4>", html, re.IGNORECASE)
        if match:
            truncated_html = html[:match.start()]
            return BeautifulSoup(truncated_html, "html.parser")
        return soup
