import traceback

from .handlers import NetworkHandler
from .models import JobData, LinkStatus
from .config import JOB_SCRAPER_URL


class JobScraper:
    def __init__(self):
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.url = JOB_SCRAPER_URL
        self.network_handler = NetworkHandler(self.url)
        self.job_data = JobData()

    def is_valid_link(self, search_term, url):
        """
        Checks if the url contains the search_term and calculate valid, a boolean
        value indicating a whether the search result was present in the url.
        The resulting link is then saved to csv as either a valid or invalid link.
        valid is returned.
        """

        valid = False
        soup = self.network_handler.get_soup(url)
        if soup:
            soup_str = str(soup).lower()
            valid = search_term.lower() in soup_str
        if valid:
            link_status = LinkStatus.VALID
        else:
            link_status = LinkStatus.INVALID
        self.job_data.save_link_to_csv(search_term, url, link_status)
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
        job_links = self.network_handler.find_job_links()
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


# This now prints a dictionary where each search term maps to a list of job links
# print(scraper.validated_links)
