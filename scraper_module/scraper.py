"""
scraper.py
----------

This module provides the JobScraper class, a utility for navigating job websites.
It identifies job links based on search criteria, validates these links, and categorizes
them as either valid or invalid. The results are saved to respective CSV files.
"""

import traceback
import csv
import re
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    NoSuchElementException,
)

from .handlers import NetworkHandler
from .models import JobData, LinkStatus
from .config import (
    JOB_SCRAPER_DEFAULT_URL,
    JOB_SCRAPER_REMOTE_URL,
    COMBINED_SEARCH,
    USE_REMOTE,
)


if USE_REMOTE:
    JOB_SCRAPER_URL = JOB_SCRAPER_REMOTE_URL
else:
    JOB_SCRAPER_URL = JOB_SCRAPER_DEFAULT_URL


class JobScraper:
    """
    Scraper utility to navigate a job website, identify and validate job links
    based on search terms, and categorize them as valid or invalid links.
    """

    def __init__(self, load_network_handler=None):
        """
        Initializes an instance of the JobScraper with attributes for
        managing the request timings, the scraper's URL, network handler,
        and the job data structure.
        """
        self.last_request_time = 0
        self.time_since_last_request = 0

        # Determine URLs to use based on config
        if COMBINED_SEARCH:
            self.urls = [JOB_SCRAPER_REMOTE_URL, JOB_SCRAPER_DEFAULT_URL]
        else:
            self.urls = (
                [JOB_SCRAPER_REMOTE_URL] if USE_REMOTE else [JOB_SCRAPER_DEFAULT_URL]
            )


        # Database connectivity check
        try:
            test_job_data = JobData()
            test_job_data.session.execute(text("SELECT 1"))
            print("Database connection successful.")
        except OperationalError as e:
            print("Database connection failed. Please check your settings and server.")
            print(e)
            raise SystemExit(1)

        self.network_handlers = None
        if load_network_handler:
            self.network_handlers = [NetworkHandler(url) for url in self.urls]
            
        self.job_data = JobData()

    def is_valid_link(self, search_term, url_index, url):
        """
        Validates if the provided URL's content contains the search term.
        The link is then categorized as valid or invalid. The validity status
        (boolean) is returned. Additionally, extracts 'job_age' from the webpage.
        """
        soup = self.network_handlers[url_index].get_soup(url)
        if soup is None:
            print(f"Failed to retrieve content for URL: {url}")
            return (
                False,
                None,
            )  # Return False for validity and None for job_age if content retrieval fails
        
        # Truncate featured jobs section
        truncated_soup = NetworkHandler.truncate_featured_jobs(soup)

        # Extract visible text from the truncated soup object
        visible_text = truncated_soup.get_text(separator=" ", strip=True).lower()
        formatted_term = self.network_handlers[url_index].formatted_term.lower()
        search_term_lower = search_term.lower()

        # Special handling for C++ and C#
        if search_term_lower == "c++":
            valid = "c++" in visible_text or "c%2b%2b" in visible_text
        elif search_term_lower == "c#":
            valid = "c#" in visible_text or "c%23" in visible_text
        else:
            # Prepare regex pattern for exact phrase match with word boundaries
            pattern = rf"\b{re.escape(search_term_lower)}\b"
            valid = bool(re.search(pattern, visible_text))
            if formatted_term != search_term_lower:
                formatted_term_pattern = rf"\b{re.escape(formatted_term)}\b"
                valid = valid or bool(re.search(formatted_term_pattern, visible_text))

        if valid:
            # Extract 'job_age'
            job_age = self.extract_job_age(soup)
            return valid, job_age
        # If the search term is not found, return None for job_age
        # don't need to launch extract_job_age() for invalid jobs
        return valid, None

    def extract_job_age(self, soup):
        """
        Extracts the 'job_age' from the soup object.
        """
        spans = soup.find_all("span")
        for span in spans:
            span_lower = span.text.lower()
            if "posted" in span_lower:
                if "mo ago" in span_lower:
                    match = re.search(r"(\d+)mo", span_lower)
                    if match:
                        return int(match.group(1)) * 30
                elif "d+ ago" in span_lower:
                    return 30  # Seek caps display at 30+ days
                elif "d ago" in span_lower:
                    match = re.search(r"(\d+)d", span.text)
                    if match:
                        return int(match.group(1))
                elif "h ago" in span_lower:
                    return 0
        return None

    def process_link(self, link, search_term, url_index):
        """Process an individual link to determine its validity and action."""
        url = link.get_attribute("href").split("?")[0]
        job_number = self.job_data.extract_job_number_from_url(url)
        # link_status = self.job_data.job_in_links(job_number)
        #  for a given job_number, get the search terms and validities as a dict(search_term: validity)
        search_term_validities = self.job_data.get_search_terms_and_validities(
            job_number
        )
        if search_term in search_term_validities:
            if search_term_validities[search_term]:
                print("X", end="", flush=True)
                return
            print("x", end="", flush=True)
            return
        # this search_term is not in the database for this job_number
        valid, job_age = self.is_valid_link(search_term, url_index, url)

        if job_age is not None:
            # calculate the job creation date
            # use current date - job_age
            job_date = self.job_data.calculate_job_date(job_age)
        else:
            job_date = None

        if valid:
            self.job_data.add_or_update_link(
                search_term, url, job_number, job_date, LinkStatus.VALID
            )
            print("V", end="", flush=True)
        else:
            self.job_data.add_or_update_link(
                search_term, url, job_number, job_date, LinkStatus.INVALID
            )
            print("I", end="", flush=True)

    def process_page(self, search_term, url_index):
        """
        Processes the current page by snapshotting job URLs (strings) up front,
        then validating each URL. This avoids holding WebElements long enough to go stale.
        Includes a bounded retry in case the page is mid re-render.
        """
        max_attempts = 3
        hrefs: list[str] = []

        for attempt in range(1, max_attempts + 1):
            job_links = self.network_handlers[url_index].find_job_links()

            hrefs = []
            stale_count = 0

            for link in job_links:
                try:
                    href = link.get_attribute("href")
                    if href:
                        hrefs.append(href.split("?")[0])
                except StaleElementReferenceException:
                    stale_count += 1

            # If we got something usable, accept it.
            # If the page is stable (no stale elements), break immediately.
            # If only a couple went stale, also accept to avoid thrashing.
            if hrefs and (stale_count == 0 or stale_count < 3):
                break

            # If we got nothing (or lots of stale), loop and try again.
            # Optionally add a tiny pause if you have one in NetworkHandler.
            # self.network_handler.small_pause()

        # De-dupe URLs while preserving order
        seen = set()
        hrefs = [u for u in hrefs if not (u in seen or seen.add(u))]

        for url in hrefs:
            self.process_link_url(url, search_term, url_index)

    def process_link_url(self, url, search_term, url_index):
        """Process an individual URL to determine its validity and action."""
        job_number = self.job_data.extract_job_number_from_url(url)

        # For a given job_number, get dict(search_term: validity)
        search_term_validities = self.job_data.get_search_terms_and_validities(
            job_number
        )

        # If we've already seen this job_number for this search_term, short-circuit
        if search_term in search_term_validities:
            self.job_data.set_not_expired(job_number)
            print(
                "X" if search_term_validities[search_term] else "x", end="", flush=True
            )
            return

        # This search_term is not in the database for this job_number yet
        valid, job_age = self.is_valid_link(search_term, url_index, url)
        job_date = (
            self.job_data.calculate_job_date(job_age) if job_age is not None else None
        )

        # Extract fields from the job detail page
        soup = self.network_handlers[url_index].get_soup(url)
        salary = self.extract_salary(soup) if soup else None
        position = self.extract_position(soup) if soup else None
        advertiser = self.extract_advertiser(soup) if soup else None
        location = self.extract_location(soup) if soup else None
        work_type = self.extract_work_type(soup) if soup else None

        self.job_data.add_or_update_link(
            search_term,
            url,
            job_number,
            job_date,
            LinkStatus.VALID if valid else LinkStatus.INVALID,
            salary=salary,
            position=position,
            advertiser=advertiser,
            location=location,
            work_type=work_type,
        )

        print("V" if valid else "I", end="", flush=True)

    def extract_salary(self, soup):
        """
        Extracts the salary string from the job detail page soup.
        """
        salary_span = soup.find("span", {"data-automation": "job-detail-salary"})
        if salary_span:
            return salary_span.get_text(strip=True)
        return None

    def extract_position(self, soup):
        tag = soup.find("h1", {"data-automation": "job-detail-title"})
        return tag.get_text(strip=True) if tag else None

    def extract_advertiser(self, soup):
        tag = soup.find("span", {"data-automation": "advertiser-name"})
        if tag:
            return tag.contents[0].strip() if tag.contents else tag.get_text(strip=True)
        return None

    def extract_location(self, soup):
        tag = soup.find("span", {"data-automation": "job-detail-location"})
        if tag:
            # Get the full text, including "(Remote)" or other suffixes
            return tag.get_text(strip=True)
        return None

    def extract_work_type(self, soup):
        tag = soup.find("span", {"data-automation": "job-detail-work-type"})
        if tag:
            a_tag = tag.find("a")
            return a_tag.get_text(strip=True) if a_tag else tag.get_text(strip=True)
        return None

    def open_cpp_search_page(self, page_number, url_index):
        """
        Opens the C++ search results page and advances to the specified page_number.
        Page 1 is loaded by entering 'C++' in the search box and submitting.
        For page_number > 1, clicks the 'Next' button (page_number - 1) times.
        Returns True if the target page is reached, False otherwise.
        """
        self.network_handlers[url_index].initiate_search("C++")
        current_page = 1
        if page_number <= 1:
            return True
        while current_page < page_number:
            if not self.network_handlers[url_index].click_next_button():
                return False
            current_page += 1
        return True
    
    def refresh_all_handlers(self):
        """
        Refreshes all network handlers to keep their sessions alive.
        """
        if not self.network_handlers:
            return
        for idx, handler in enumerate(self.network_handlers):
            try:
                print(f"Refreshing handler {idx} for URL: {self.urls[idx]}")
                handler.refresh()
            except Exception as e:
                print(f"Failed to refresh handler {idx} for URL: {self.urls[idx]} with error: {e}")

    def perform_searches(self, search_terms):
        """
        Drives the job scraping process:

        1. Searches the job website for each term in the provided search terms.
        2. Extracts job links from the search results.
        3. Validates each job link based on its content.
        4. Categorizes and saves each link as either valid or invalid.
        5. Repeats the process for every subsequent page of results until
        no further pages exist.

        Exceptions (including manual interrupts) are gracefully handled,
        and relevant messages are displayed.
        """
        # Load saved state (if any)
        saved_state = self.load_state()
        start_from_term = None
        start_from_url_index = None
        start_from_page = 1
        keepalive_counter = 0
        keepalive_every_pages = 5

        if saved_state is not None:
            start_from_term = saved_state["search_term"]
            start_from_url_index = saved_state["url_index"]
            start_from_page = saved_state["page_number"]

        search_term = None
        page_number = None

        try:
            
            for search_term in search_terms:
                if start_from_term is not None and search_term != start_from_term:
                    continue  # Skip terms until you reach the saved state

                for url_index, url in enumerate(self.urls):
                    if start_from_url_index is not None and url != self.urls[start_from_url_index]:
                        continue  # Skip URLs until you reach the saved state

                    print(f"\nProcessing search '{search_term}' from: {url}")
                    page_number = start_from_page
                    if search_term.strip().lower() != "c++":
                        self.network_handlers[url_index].initiate_search(search_term)

                        search_base = self.network_handlers[url_index].search_base
                        page_param_sep = self.network_handlers[url_index].page_param_sep

                        while True:
                            page_url = (
                                f"{search_base}{page_param_sep}page={page_number}"
                                if page_number > 1
                                else search_base
                            )

                            if page_number > 1:
                                print("\n")
                            print(f"page {page_number}")
                            self.network_handlers[url_index].driver.get(page_url)
                            self.network_handlers[url_index].selenium_interaction_delay()
                            self.process_page(search_term, url_index)
                            self.save_state(search_term, url_index, page_number)

                            soup = self.network_handlers[url_index].get_soup(page_url)
                            if not self.network_handlers[url_index].has_results(soup):
                                break

                            page_number += 1
                            keepalive_counter += 1
                            if keepalive_counter % keepalive_every_pages == 0:
                                self.refresh_all_handlers()
                    else:
                        while True:
                            try:
                                if not self.open_cpp_search_page(page_number, url_index):
                                    print(f"Failed to reach page {page_number} for C++ search.")
                                    break
                                print(f"page {page_number}")
                                self.process_page(search_term, url_index)
                                self.save_state(search_term, url_index, page_number)
                                soup = self.network_handlers[url_index].get_current_page_soup()
                                if not self.network_handlers[url_index].has_results(soup):
                                    break
                                keepalive_counter += 1
                                if keepalive_counter % keepalive_every_pages == 0:
                                    self.refresh_all_handlers()
                                page_number += 1
                            except (TimeoutException, NoSuchElementException):
                                print("\n\nSelenium browsing failed, likely due to inability to take focus.")
                                print("Please press ENTER when you are ready for the scraper to continue.")
                                print("After pressing ENTER, please do not interact with the screen until C++ scraping is complete.")
                                input()
                                print(f"Recreating browser window for: {self.urls[url_index]}")
                                self.network_handlers[url_index].close()
                                self.network_handlers[url_index] = NetworkHandler(self.urls[url_index])
                                print("Browser window recreated. Retrying page...")
                                # page_number is unchanged — retries the same page
                    start_from_page = 1
                    if start_from_url_index == url_index:
                        start_from_url_index = (
                            None  # Reset URL checkpoint after resuming from it
                        )
                if start_from_term == search_term:
                    start_from_term = None

            self.clear_state()

        except KeyboardInterrupt:
            print("Scraping interrupted by user.")
            if search_term is not None and page_number is not None:
                self.save_state(search_term, url_index, page_number)

        except Exception as exception:  # pylint: disable=broad-except
            if search_term is not None and page_number is not None:
                self.save_state(search_term, url_index, page_number)
            print(f"Unhandled exception occurred: {exception}")
            print("Printing stack trace...")
            traceback.print_exc()

        finally:
            try:
                print("Closing database connection...")
                self.job_data.close()
            except Exception as exception:  # pylint: disable=broad-except
                print(
                    f"Exception while trying to close the database connection: {exception}"
                )
                traceback.print_exc()

            try:
                print("Closing browser...")
                print(f"Number of live network handlers: {len(self.network_handlers) if self.network_handlers else 0}")
                for handler in self.network_handlers:
                    handler.close()
            except Exception as exception:  # pylint: disable=broad-except
                print(f"Exception while trying to close the browser: {exception}")
                traceback.print_exc()
                if search_term is not None and page_number is not None:
                    self.save_state(search_term, url_index, page_number)

    def save_state(self, search_term, url_index, page_number):
        """
        Saves the current state of the scraper to a CSV file.
        """
        with open("scraper_state.csv", "w", newline="", encoding="utf-8") as file:
            file.write("# format: search_term, url_index (0=remote, 1=all-melbourne), page_number\n")
            writer = csv.writer(file)
            writer.writerow([search_term, url_index, page_number])

    def load_state(self):
        """
        Loads the last saved state of the scraper from a CSV file.
        Returns None if the file is not found or has invalid data.
        """
        try:
            with open("scraper_state.csv", "r", encoding="utf-8") as file:
                reader = csv.reader(row for row in file if not row.startswith("#"))
                for row in reader:
                    return {
                        "search_term": row[0],
                        "url_index": int(row[1]),
                        "page_number": int(row[2]),
                    }
        except Exception:
            return None  # return if no valid data is found in the csv file

    def clear_state(self):
        """
        Clears the saved state of the scraper by emptying the CSV file.
        """
        with open("scraper_state.csv", "w", newline="", encoding="utf-8") as file:
            pass


def print_legend():
    print("\nLegend:")
    print("V = Valid link (new)")
    print("I = Invalid link (new)")
    print("X = Already validated as valid")
    print("x = Already validated as invalid")


# Call this at the start or end of your main script
print_legend()
