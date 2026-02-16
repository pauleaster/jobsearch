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

from .handlers import NetworkHandler
from .models import JobData, LinkStatus
from .config import JOB_SCRAPER_DEFAULT_URL, JOB_SCRAPER_REMOTE_URL

USE_REMOTE = (
    False  # Set this constant to either True or False based on your requirements
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
        self.url = JOB_SCRAPER_URL

        # Database connectivity check
        try:
            test_job_data = JobData()
            test_job_data.session.execute(text("SELECT 1"))
            print("Database connection successful.")
        except OperationalError as e:
            print("Database connection failed. Please check your settings and server.")
            print(e)
            raise SystemExit(1)

        if load_network_handler:
            self.network_handler = NetworkHandler(self.url)
        else:
            self.network_handler = None
        self.job_data = JobData()

    def is_valid_link(self, search_term, url):
        """
        Validates if the provided URL's content contains the search term.
        The link is then categorized as valid or invalid. The validity status
        (boolean) is returned. Additionally, extracts 'job_age' from the webpage.
        """
        soup = self.network_handler.get_soup(url)
        if soup is None:
            print(f"Failed to retrieve content for URL: {url}")
            return False, None  # Return False for validity and None for job_age if content retrieval fails
        # Extract visible text from the soup object
        visible_text = soup.get_text(separator=" ", strip=True).lower()

        # Prepare regex pattern for exact phrase match with word boundaries
        pattern = rf"\b{re.escape(search_term.lower())}\b"
        valid = bool(re.search(pattern, visible_text))

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
        # Look for all span tags, and then filter out the one with 'Posted xd ago'
        spans = soup.find_all("span")
        for span in spans:
            span_lower = span.text.lower()
            if "posted" in span_lower:
                if "d ago" in span_lower:
                    # Extract the number before 'd'
                    match = re.search(r"(\d+)d", span.text)
                    if match:
                        return int(match.group(1))
                elif "h ago" in span.text.lower():
                    # Extract the number before 'h'
                    match = re.search(r"(\d+)h", span.text)
                    if match:
                        return 0  # 0 days ago
        return None

    def process_link(self, link, search_term):
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
        valid, job_age = self.is_valid_link(search_term, url)

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

    def process_page(self, search_term):
        """
        Processes the current page by snapshotting job URLs (strings) up front,
        then validating each URL. This avoids holding WebElements long enough to go stale.
        Includes a bounded retry in case the page is mid re-render.
        """
        max_attempts = 3
        hrefs: list[str] = []

        for attempt in range(1, max_attempts + 1):
            job_links = self.network_handler.find_job_links()

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
            self.process_link_url(url, search_term)

    def process_link_url(self, url, search_term):
        """Process an individual URL to determine its validity and action."""
        job_number = self.job_data.extract_job_number_from_url(url)

        # For a given job_number, get dict(search_term: validity)
        search_term_validities = self.job_data.get_search_terms_and_validities(job_number)

        # If we've already seen this job_number for this search_term, short-circuit
        if search_term in search_term_validities:
            print("X" if search_term_validities[search_term] else "x", end="", flush=True)
            return

        # This search_term is not in the database for this job_number yet
        valid, job_age = self.is_valid_link(search_term, url)
        job_date = self.job_data.calculate_job_date(job_age) if job_age is not None else None

        self.job_data.add_or_update_link(
            search_term,
            url,
            job_number,
            job_date,
            LinkStatus.VALID if valid else LinkStatus.INVALID,
        )

        print("V" if valid else "I", end="", flush=True)

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
        start_from_term = False  # Set initial value to False
        start_from_page = 1

        if saved_state is not None:
            start_from_term = saved_state["search_term"]
            start_from_page = saved_state["page_number"]

        try:
            for search_term in search_terms:
                if start_from_term and search_term != start_from_term:
                    continue  # Skip terms until you reach the saved state

                print(f"\nProcessing search {search_term}")
                self.network_handler.initiate_search(search_term)
                base_url, location = self.network_handler.extract_base_and_location()
                formatted_term = self.network_handler.format_search_term(search_term)
                search_base = f"{base_url}/{formatted_term}-jobs/{location}"

                page_number = start_from_page
                while True:
                    page_url = (
                        f"{search_base}?page={page_number}" if page_number > 1 else search_base
                    )
                    print(f"page {page_number}")
                    self.network_handler.driver.get(page_url)
                    self.network_handler.selenium_interaction_delay()
                    self.process_page(search_term)

                    # Check if there are results on this page
                    soup = self.network_handler.get_soup(page_url)
                    if not self.network_handler.has_results(soup):
                        break

                    page_number += 1

                start_from_page = 1
                if start_from_term == search_term:
                    start_from_term = False
            self.clear_state()

        except KeyboardInterrupt:
            print("Scraping interrupted by user.")
            # Save state before exiting
            self.save_state(search_term, page_number)
        except Exception as exception:  # pylint: disable=broad-except
            # unhandled exception
            print(f"Unhandled exception occurred: {exception}")
            print("Printing stack trace...")
            traceback.print_exc()
        finally:
            # attempt to close the browser
            try:
                print("Closing browser...")
                self.network_handler.close()
            except Exception as exception:  # pylint: disable=broad-except
                print(f"Exception while trying to close the browser: {exception}")
                traceback.print_exc()
                # Save state before exiting
                self.save_state(search_term, page_number)

            # attempt to close the database connection
            try:
                print("Closing database connection...")
                self.job_data.close()
            except Exception as exception:  # pylint: disable=broad-except
                print(
                    f"Exception while trying to close the database connection: {exception}"
                )
                traceback.print_exc()

    def save_state(self, search_term, page_number):
        """
        Saves the current state of the scraper to a CSV file.
        """
        with open("scraper_state.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([search_term, page_number])

    def load_state(self):
        """
        Loads the last saved state of the scraper from a CSV file.
        Returns None if the file is not found or has invalid data.
        """
        try:
            with open("scraper_state.csv", "r", encoding="utf-8") as file:
                reader = csv.reader(file)
                for row in reader:
                    return {"search_term": row[0], "page_number": int(row[1])}
            return None  # Empty file
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
