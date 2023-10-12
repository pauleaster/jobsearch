"""
scraper.py
----------

This module provides the JobScraper class, a utility for navigating job websites.
It identifies job links based on search criteria, validates these links, and categorizes
them as either valid or invalid. The results are saved to respective CSV files.
"""
import traceback

from .handlers import NetworkHandler
from .models import JobData, LinkStatus
from .config import JOB_SCRAPER_DEFAULT_URL, JOB_SCRAPER_REMOTE_URL

USE_REMOTE = False  # Set this constant to either True or False based on your requirements

if USE_REMOTE:
    JOB_SCRAPER_URL = JOB_SCRAPER_REMOTE_URL
else:
    JOB_SCRAPER_URL = JOB_SCRAPER_DEFAULT_URL


class JobScraper:
    """
    Scraper utility to navigate a job website, identify and validate job links
    based on search terms, and categorize them as valid or invalid links.
    """

    def __init__(self):
        """
        Initializes an instance of the JobScraper with attributes for
        managing the request timings, the scraper's URL, network handler,
        and the job data structure.
        """
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.url = JOB_SCRAPER_URL
        self.network_handler = NetworkHandler(self.url)
        self.job_data = JobData()

    def is_valid_link(self, search_term, url):
        """
        Validates if the provided URL's content contains the search term.
        The link is then categorized as valid or invalid and saved to the
        respective CSV. The validity status (boolean) is returned.
        """

        valid = False
        soup = self.network_handler.get_soup(url)
        if soup:
            soup_str = str(soup).lower()
            search_terms = search_term.lower().split()
            valid = all(term in soup_str for term in search_terms)
            
        if valid:
            link_status = LinkStatus.VALID
        else:
            link_status = LinkStatus.INVALID
        self.job_data.save_link(search_term, url, link_status)
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
        """
        Processes the current page, extracting job links and evaluating
        each link's validity based on the given search term.
        """
        job_links = self.network_handler.find_job_links()
        for link in job_links:
            self.process_link(link, search_term)

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
        try:
            for search_term in search_terms:
                print(f"Processing search {search_term}")
                # enter search term and submit
                self.network_handler.initiate_search(search_term)
                page_number = 1
                print(f"page {page_number}")

                has_next_page = True
                while has_next_page:
                    self.process_page(search_term)

                    has_next_page = self.network_handler.click_next_button()
                    # Try to find the "Next" button and click it
                    if has_next_page:
                        page_number += 1
                        print(f"\npage {page_number}")

        except KeyboardInterrupt:
            print("Scraping interrupted by user.")
        except Exception as exception: # pylint: disable=broad-except
            # unhandled exception
            print(f"Unhandled exception occurred: {exception}")
            print("Printing stack trace...")
            traceback.print_exc()
        finally:
            # attempt to close the browser
            try:
                print("Closing browser...")
                self.network_handler.close()
            except Exception as exception: # pylint: disable=broad-except
                print(f"Exception while trying to close the browser: {exception}")
                traceback.print_exc()

