import time
import traceback
import csv
import os
from enum import Enum, auto
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys
import requests
from bs4 import BeautifulSoup
from filelock import FileLock


class DelaySettings(Enum):
    """
    Delay constants for network handling
    """

    SELENIUM_INTERACTION_DELAY = 10
    SUCCESSIVE_URL_READ_DELAY = 20
    REQUEST_EXCEPTION_DELAY = 30
    REQUEST_TIMEOUT = 10
    NUM_RETRIES = 4


class NetworkHandler:
    """
    Handles web access using delays from DelaySettings.
    """

    def __init__(self, url):
        self.successive_url_read_delay = DelaySettings.SUCCESSIVE_URL_READ_DELAY
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, self.successive_url_read_delay)
        print(f"Opening {url}")
        self.driver.get(url)

    def selenium_interaction_delay(self):
        """Handles the delay for Selenium interactions to ensure the browser has time to react."""
        time.sleep(DelaySettings.SELENIUM_INTERACTION_DELAY)

    def find_elements(self, by, value): # pylint: disable=invalid-name
        elements = self.driver.find_elements(by, value)
        self.selenium_interaction_delay()
        return elements

    def initiate_search(self, search_term):
        search_field = self.driver.find_element(By.ID, "keywords-input")
        search_field.send_keys(Keys.CONTROL + "a")
        search_field.send_keys(Keys.DELETE)
        search_field.send_keys(search_term)
        search_field.send_keys(Keys.RETURN)
        self.selenium_interaction_delay()  # Add the delay after initiating the search

    def click_next_button(self):
        next_button = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//a[starts-with(@data-automation, "page-") and @aria-label="Next"]',
                )
            )
        )
        next_button.click()
        self.selenium_interaction_delay()

    def handle_successive_url_read_delay(self):
        """
        Handles the delay between successive URL reads to adhere to a specific delay setting.

        1. Calculates the time since the last request.
        2. If this time is less than the configured SUCCESSIVE_URL_READ_DELAY,
            sleeps for the remaining time.
        3. Resets the last request time to the current time.
        """
        self.time_since_last_request = time.time() - self.last_request_time
        if self.time_since_last_request < DelaySettings.SUCCESSIVE_URL_READ_DELAY:
            time.sleep(
                DelaySettings.SUCCESSIVE_URL_READ_DELAY - self.time_since_last_request
            )
        self.last_request_time = time.time()

    def get_request(self, url):
        """
        Returns a requests object for the given URL.
        self.last_request_time is updated to the current time.
        If a requests.RequestException is raised, the request is retried up
        to NUM_RETRIES times.
        The time between each retry is set to REQUEST_EXCEPTION_DELAY.
        """

        last_exception = None
        for _ in range(DelaySettings.NUM_RETRIES):
            try:
                request = requests.get(url, timeout=DelaySettings.REQUEST_TIMEOUT)
                self.last_request_time = time.time()
                return request
            except requests.RequestException as exception:
                last_exception = exception
                print("E", end="")
                time.sleep(DelaySettings.REQUEST_EXCEPTION_DELAY)
        raise last_exception

    def get_soup(self, url):
        """
        Returns a BeautifulSoup object for the given URL.
        The network is not accessed until the time since the last request,
        is greater than the configured SUCCESSIVE_URL_READ_DELAY.
        Finally, self.last_request_time is set to the current time.
        """
        self.handle_successive_url_read_delay()
        response = self.get_request(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        else:
            soup = None
        self.last_request_time = time.time()  # Set time since last request
        return soup

    def close(self):
        self.driver.quit()


class LinkStatus(Enum):
    """
    Flag to indicate whether the links are valid or not.
    Used as a key in the links dictionary.
    """

    VALID = auto()
    INVALID = auto()


class JobData:
    def __init__(self):
        self.links = {LinkStatus.VALID: {}, LinkStatus.INVALID: {}}

        # A dictionary for storing job numbers for each search_term
        self.job_numbers = {LinkStatus.VALID: set(), LinkStatus.INVALID: set()}
        self.csv_files = {
            LinkStatus.VALID: "validated_links.csv",
            LinkStatus.INVALID: "invalidated_links.csv",
        }

        self.lockfilenames = {
            LinkStatus.VALID: "validated_lockfile",
            LinkStatus.INVALID: "invalidated_lockfile",
        }

        self.locks = {
            LinkStatus.VALID: FileLock(self.lockfilenames[LinkStatus.VALID]),
            LinkStatus.INVALID: FileLock(self.lockfilenames[LinkStatus.INVALID]),
        }
        # Check for lock files and delete if they exist
        self.delete_lockfiles()

        self.read_csv_files()

        # Store the initial counts
        self.initial_counts = {
            LinkStatus.VALID: self.get_link_count(LinkStatus.VALID),
            LinkStatus.INVALID: self.get_link_count(LinkStatus.INVALID),
        }

        print(
            f"Initial Validated links #{scraper.job_data.get_link_count(LinkStatus.VALID)}"
        )
        print(
            f"Initial Invalidated links #{scraper.job_data.get_link_count(LinkStatus.INVALID)}"
        )

    def get_link_count(self, status: LinkStatus) -> int:
        """Return the current count of links for a specific status."""
        return sum(len(links) for links in self.links[status].values())

    def get_links_difference(self, status: LinkStatus) -> int:
        """
        Return the difference between initial and current count of links
        for a specific status."""
        return self.get_link_count(status) - self.initial_counts[status]

    def delete_lockfiles(self):
        """Deletes the lockfiles."""
        for lockfile in self.lockfilenames.values():
            if os.path.exists(lockfile):
                os.remove(lockfile)
                print(f"Removed lockfile: {lockfile}")

    def save_link_to_csv(self, search_term, url, status: LinkStatus):
        """
        Saves the current link to validated_links.csv
        or invalidated_links.csv depending on whether the link is valid or not
        and closes the file.
        """

        csv_file = self.csv_files[status]
        lock = self.locks[status]
        with lock:
            with open(csv_file, "a", newline="", encoding="utf-8") as file:
                csv_writer = csv.writer(file)
                job_number = url.split("/")[-1]
                csv_writer.writerow([search_term, url, job_number])

    def read_csv_files(self):
        """
        Reads the validated_links.csv and invalidated_links.csv files
        and recreates the validated_links and invalidated_links dictionaries
        from the data in the files and then closes the files.
        """
        for status in LinkStatus:
            link_dict = self.links[status]
            job_numbers_set = self.job_numbers[status]
            lock = self.locks[status]
            with lock:
                if os.path.exists(self.csv_files[status]):
                    with open(self.csv_files[status], "r", encoding="utf-8") as file:
                        csv_reader = csv.reader(file)
                        for row in csv_reader:
                            search_term, url, job_number = row
                            if search_term not in link_dict.keys():
                                link_dict[search_term] = []
                            link_dict[search_term].append([url, job_number])
                            job_numbers_set.add(job_number)

    def job_in_links(self, job):
        """
        Returns a dictionary of booleans indicating whether the job is present in
        the validated_links or invalidated_links dictionaries for any search_term.
        The dictionary keys are LinkStatus.VALID and LinkStatus.INVALID.
        """
        results = {}
        for status in LinkStatus:
            results[status] = job in self.job_numbers[status]
        return results

    def add_new_link(self, search_term, url, job_number, status: LinkStatus):
        """
        Adds a new link to the links dictionary depending on the link's status.
        """
        if search_term not in self.links[status]:
            self.links[status][search_term] = []
        self.links[status][search_term].append([url, job_number])
        self.job_numbers[status].add(job_number)


class JobScraper:
    def __init__(self):
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.url = "https://www.seek.com.au/jobs/in-All-Melbourne-VIC"
        self.network_handler = NetworkHandler(self.url)
        self.job_data = JobData()

    def is_valid_link(self, search_term, url):
        """
        Checks if the url contains the search_term and calculate valid, a boolean
        value indicating a whether the search result was present in the url.
        The resulting link is then saved to csv as either a valid or invalid link.
        valid is returned.
        """

        soup = self.network_handler.get_soup(url)
        if soup:
            soup_str = str(soup).lower()
            valid = search_term.lower() in soup_str
        else:
            valid = False
        self.job_data.save_link_to_csv(search_term, url, valid)
        return valid

    def process_link(self, link, search_term):
        """Process an individual link to determine its validity and action."""
        url = link.get_attribute("href").split("?")[0]
        job_number = url.split("/")[-1]
        link_status = self.job_data.job_in_links(job_number)

        if link_status[LinkStatus.VALID]:
            print("X", end="", flush=True)
            return
        if link_status[LinkStatus.INVALID]:
            print("x", end="", flush=True)
            return

        if self.is_valid_link(search_term, url):
            self.job_data.add_new_link(search_term, url, job_number, LinkStatus.VALID)
            print("V", end="", flush=True)
        else:
            self.job_data.add_new_link(search_term, url, job_number, LinkStatus.INVALID)
            print("I", end="", flush=True)

    def process_page(self, search_term):
        """Process the current page for job links and action on them."""
        job_links = self.network_handler.find_elements(
            By.XPATH, '//a[contains(@href, "/job/")]'
        )
        for link in job_links:
            self.process_link(link, search_term)

    def perform_searches(self, search_terms):
        """
        Search the job website for each search term in search_terms.
        Parse the search result and extract links to jobs.
        For each link, load up the job description.
        Validate the resulting job by double checking that the search term
        is in the job description.
        If it is then add the job to the validated_links dictionary.
        Otherwise add it to the invalidated_links dictionary.
        After the search result has been parsed, click on the next page button
        and repeat the process until there are no more pages.
        """
        try:
            for search_term in search_terms:
                print(f"Processing search {search_term}")
                # initialise an empty list if key does not exist
                for status in LinkStatus:
                    if search_term not in self.job_data.links[status]:
                        self.job_data.links[status][search_term] = []

                # enter search term and submit
                self.network_handler.initiate_search(search_term)
                page_number = 1
                print(f"page {page_number}")

                while True:
                    try:
                        self.process_page(search_term)

                        # Try to find the "Next" button and click it
                        self.network_handler.click_next_button()
                        page_number += 1
                        print(f"page {page_number}")
                    except (
                        ElementClickInterceptedException,
                        NoSuchElementException,
                        TimeoutException,
                    ):
                        # If the "Next" button is not found, we've reached the last page
                        break
        except KeyboardInterrupt:
            print("Scraping interrupted by user.")
        except Exception as exception:
            # unhandled exception
            print(f"Unhandled exception occurred: {exception}")
            print("Printing stack trace...")
            traceback.print_exc()
        finally:
            # attempt to close the browser
            try:
                print("Closing browser...")
                self.network_handler.close()
            except Exception as exception:
                print(f"Exception while trying to close the browser: {exception}")
                traceback.print_exc()
            self.job_data.delete_lockfiles()


if __name__ == "__main__":
    # Usage:
    scraper = JobScraper()
    scraper.perform_searches(["software developer"])
    print(
        f"Validated links length: {scraper.job_data.get_link_count(LinkStatus.VALID)}"
    )
    print(
        f"Invalidated links length: {scraper.job_data.get_link_count(LinkStatus.INVALID)}"
    )
    print(
        f"Valid links read: {scraper.job_data.get_links_difference(LinkStatus.VALID)}"
    )
    print(
        f"Invalid links read: {scraper.job_data.get_links_difference(LinkStatus.INVALID)}"
    )


# This now prints a dictionary where each search term maps to a list of job links
# print(scraper.validated_links)
