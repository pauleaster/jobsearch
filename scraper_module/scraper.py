"""
scraper.py
----------

This module provides the JobScraper class, a utility for navigating job websites.
It identifies job links based on search criteria, validates these links, and categorizes
them as either valid or invalid. The results are saved to respective CSV files.
"""
import traceback
import csv

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

    def __init__(self, load_network_handler=None):
        """
        Initializes an instance of the JobScraper with attributes for
        managing the request timings, the scraper's URL, network handler,
        and the job data structure.
        """
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.url = JOB_SCRAPER_URL
        if load_network_handler:
            self.network_handler = NetworkHandler(self.url)
        else:
            self.network_handler = None
        self.job_data = JobData()

    def is_valid_link(self, search_term, url):
        """
        Validates if the provided URL's content contains the search term.
        The link is then categorized as valid or invalid. The validity status 
        (boolean) is returned.
        """


        soup = self.network_handler.get_soup(url)
        search_terms = search_term.lower().split()
        soup_str = str(soup).lower()
        valid = all(term in soup_str for term in search_terms)

        return valid



    def process_link(self, link, search_term):
        """Process an individual link to determine its validity and action."""
        url = link.get_attribute("href").split("?")[0]
        job_number = self.job_data.extract_job_number_from_url(url)
        # link_status = self.job_data.job_in_links(job_number)
        #  for a given job_number, get the search terms and validities as a dict(search_term: validity)
        search_term_validities = self.job_data.get_search_terms_and_validities(job_number)
        if search_term in search_term_validities:
            if search_term_validities[search_term]:
                print("X", end="", flush=True)
                return
            print("x", end="", flush=True)
            return
        # this search_term is not in the database for this job_number
        valid  = self.is_valid_link(search_term, url)

        if valid:
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
        # Load saved state (if any)
        saved_state = self.load_state()
        start_from_term = False  # Set initial value to False
        start_from_page = 1

        if saved_state is not None:
            start_from_term = saved_state['search_term']
            start_from_page = saved_state['page_number']


        try:
            for search_term in search_terms:
                if start_from_term and search_term != start_from_term:
                    continue  # Skip terms until you reach the saved state

                print(f"\nProcessing search {search_term}")
                # enter search term and submit
                self.network_handler.initiate_search(search_term)
                page_number = 1
                has_next_page = True
                while (page_number < start_from_page) and has_next_page:
                    has_next_page = self.network_handler.click_next_button()
                    page_number += 1

                if has_next_page:
                    print(f"page {page_number}")
                    while has_next_page:
                        if page_number >= start_from_page:
                            self.process_page(search_term)

                            # Save state
                            self.save_state(search_term, page_number + 1)


                        has_next_page = self.network_handler.click_next_button()
                        # Try to find the "Next" button and click it
                        if has_next_page:
                            page_number += 1
                            print(f"\npage {page_number}")

                # Reset start_from_page after completing the term where it left off
                start_from_page = 1
                # After processing the saved search term, reset start_from_term
                if start_from_term == search_term:
                    start_from_term = False


        except KeyboardInterrupt:
            print("Scraping interrupted by user.")
            # Save state before exiting
            self.save_state(search_term, page_number)
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
                # Save state before exiting
                self.save_state(search_term, page_number)
            
            # attempt to close the database connection
            try:
                print("Closing database connection...")
                self.job_data.db_handler.close()
            except Exception as exception: # pylint: disable=broad-except
                print(f"Exception while trying to close the database connection: {exception}")
                traceback.print_exc()

    def save_state(self, search_term, page_number):
        """
        Saves the current state of the scraper to a CSV file.
        """
        with open('scraper_state.csv', 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([search_term, page_number])

    def load_state(self):
        """
        Loads the last saved state of the scraper from a CSV file.
        Returns None if the file is not found or has invalid data.
        """
        try:
            with open('scraper_state.csv', 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    return {'search_term': row[0], 'page_number': int(row[1])}
            return None  # Empty file
        except Exception:
            return None  # return if no valid data is found in the csv file
