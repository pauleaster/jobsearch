from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys
import time
import requests
from bs4 import BeautifulSoup
import traceback
import csv
import os
from filelock import FileLock

class DelaySettings:
    SELENIUM_INTERACTION_DELAY = 10
    SUCCESSIVE_URL_READ_DELAY = 20
    REQUEST_EXCEPTION_DELAY = 30
    NUM_RETRIES = 4



class NetworkHandler:
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

    def find_elements(self, by, value):
        elements = self.driver.find_elements(by, value)
        self.selenium_interaction_delay()
        return elements

    def initiate_search(self, search_term):
        search_field = self.driver.find_element(By.ID, "keywords-input")
        search_field.send_keys(Keys.CONTROL + 'a')
        search_field.send_keys(Keys.DELETE)
        search_field.send_keys(search_term)
        search_field.send_keys(Keys.RETURN)
        self.selenium_interaction_delay()  # Add the delay after initiating the search

    def click_next_button(self):
        next_button = self.wait.until(EC.presence_of_element_located(
            (By.XPATH, '//a[starts-with(@data-automation, "page-") and @aria-label="Next"]')))
        next_button.click()
        self.selenium_interaction_delay()

    def handle_successive_url_read_delay(self):
        """
        Handles the delay between successive URL reads to adhere to a specific delay setting.

        1. Calculates the time since the last request.
        2. If this time is less than the configured SUCCESSIVE_URL_READ_DELAY, sleeps for the remaining time.
        3. Resets the last request time to the current time.
        """
        self.time_since_last_request = time.time() - self.last_request_time
        if self.time_since_last_request < DelaySettings.SUCCESSIVE_URL_READ_DELAY:
            time.sleep(DelaySettings.SUCCESSIVE_URL_READ_DELAY -
                    self.time_since_last_request)
        self.last_request_time = time.time()


    def get_request(self, url):
        """
        Returns a requests object for the given URL.
        self.last_request_time is updated to the current time.
        If a requests.RequestException is raised, the request is retried up to NUM_RETRIES times.
        The time between each retry is set to REQUEST_EXCEPTION_DELAY.
        """

        last_exception = None
        for _ in range(DelaySettings.NUM_RETRIES):
            try:
                request =  requests.get(url)
                self.last_request_time = time.time()
                return request
            except requests.RequestException as e:
                last_exception = e
                print('E', end = '')
                time.sleep(DelaySettings.REQUEST_EXCEPTION_DELAY)
        raise last_exception
    
    def get_soup(self, url):
        """
        Returns a BeautifulSoup object for the given URL.
        The network is not accessed until the time since the last request is greater than the configured SUCCESSIVE_URL_READ_DELAY.
        Finally, self.last_request_time is set to the current time.
        """
        self.handle_successive_url_read_delay()
        response = self.get_request(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
        else:
            soup = None
        self.last_request_time = time.time() # Set time since last request
        return soup


    def close(self):
        self.driver.quit()

class JobData:
    def __init__(self):
        self.validated_links = {}
        self.invalidated_links = {}
        self.validated_csv_file = 'validated_links.csv'
        self.invalidated_csv_file = 'invalidated_links.csv'
        self.validated_lockfilename = "validated_lockfile"
        self.invalidated_lockfilename = "invalidated_lockfile"
        # Check for lock files and delete if they exist
        self.delete_lockfiles()
        self.validated_lock = FileLock(self.validated_lockfilename)
        self.invalidated_lock = FileLock(self.invalidated_lockfilename)

        self.read_csv_files()
        self.final_validated_links_length = self.initial_validated_links_length
        self.final_invalidated_links_length = self.initial_invalidated_links_length
        print(f"len validated_links: {self.initial_validated_links_length}")
        print(f"len invalidated_links: {self.initial_invalidated_links_length}")

    def delete_lockfiles(self):
        """Deletes the lockfiles."""
        for lockfile in [self.validated_lockfilename, self.invalidated_lockfilename]:
            if os.path.exists(lockfile):
                os.remove(lockfile)
                print(f"Removed lockfile: {lockfile}")


    def save_link_to_csv(self, search_term, url, valid):
        """
            Saves the current link to validated_links.csv
            or invalidated_links.csv depending on whether the link is valid or not
            and closes the file.
        """

        if valid:
            csv_file = self.validated_csv_file
            lock = self.validated_lock
        else:
            csv_file = self.invalidated_csv_file
            lock = self.invalidated_lock
        with lock:
            with open(csv_file, 'a', newline='') as file:
                csv_writer = csv.writer(file)
                job_number = url.split('/')[-1]
                csv_writer.writerow([search_term, url, job_number])

    def read_csv_files(self):
        """
        Reads the validated_links.csv and invalidated_links.csv files
        and recreates the validated_links and invalidated_links dictionaries
        from the data in the files and then closes the files.
        """
        self.initial_validated_links_length = 0
        self.initial_invalidated_links_length = 0
        with self.validated_lock:
            if os.path.exists(self.validated_csv_file):
                with open(self.validated_csv_file, 'r') as file:
                    csv_reader = csv.reader(file)
                    for row in csv_reader:
                        search_term, link,job_number = row
                        if search_term not in self.validated_links.keys():
                            self.validated_links[search_term] = []
                        self.validated_links[search_term].append([link, job_number])
                        self.initial_validated_links_length += 1

        with self.invalidated_lock:
            if os.path.exists(self.invalidated_csv_file):
                with open(self.invalidated_csv_file, 'r') as file:
                    csv_reader = csv.reader(file)
                    for row in csv_reader:
                        search_term, link, job_number = row
                        if search_term not in self.invalidated_links.keys():
                            self.invalidated_links[search_term] = []
                        self.invalidated_links[search_term].append([link, job_number])
                        self.initial_invalidated_links_length += 1

    def job_in_links(self, job, search_term):
        """
        get all the job numbers from the validated_links[search_term] and 
        invalidated_links dictionaries[search_term] and return a tuple whether 
        the job is already present in (validated_links, invalidated_links)
        """
        validated_jobs =[]
        invalidated_jobs = []
        for (_, job_number) in self.validated_links[search_term]:
            validated_jobs.append(job_number)
        for (_, job_number) in self.invalidated_links[search_term]:
            invalidated_jobs.append(job_number)
        return (job in validated_jobs, job in invalidated_jobs)



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
                if search_term not in self.job_data.validated_links:
                    self.job_data.validated_links[search_term] = []
                if search_term not in self.job_data.invalidated_links:
                    self.job_data.invalidated_links[search_term] = []
                # enter search term and submit
                self.network_handler.initiate_search(search_term)
                page_number = 1
                print(f"page {page_number}")
                while True:
                    try:
                        # Code to scrape job links from the current page...
                        job_links = self.network_handler.find_elements(By.XPATH, '//a[contains(@href, "/job/")]')
                        for link in job_links:
                            url = link.get_attribute('href').split("?")[0]
                            job_number = url.split("/")[-1]
                            (validated_job, invalidated_job) = self.job_data.job_in_links(job_number, search_term)

                            if validated_job :
                                print("X", end="", flush=True)
                                continue
                            elif invalidated_job:
                                print("x", end="", flush=True)
                                continue
                            if self.is_valid_link(search_term, url):
                                self.job_data.validated_links[search_term].append([url, job_number])
                                self.job_data.final_validated_links_length += 1
                                print("V", end="")
                            else:
                                self.job_data.invalidated_links[search_term].append([url, job_number])
                                self.job_data.final_invalidated_links_length += 1
                                print("I", end="", flush=True)
                        print()
                        # Try to find the "Next" button and click it
                        self.network_handler.click_next_button()
                        page_number += 1
                        print(f"page {page_number}")
                    except (ElementClickInterceptedException, NoSuchElementException, TimeoutException):
                        # If the "Next" button is not found, we've reached the last page
                        break
        except KeyboardInterrupt:
            print("Scraping interrupted by user.")

        except Exception as e:
            # unhandled exception
            print(f"Unhandled exception occurred: {e}")
            print("Printing stack trace...")
            traceback.print_exc()

        finally:
            # attempt to close the browser
            try:
                print("Closing browser...")
                self.network_handler.close()
            except Exception as e:
                print(f"Exception while trying to close the browser: {e}")
                traceback.print_exc()
            self.job_data.delete_lockfiles()



if __name__ == "__main__":
    # Usage:
    scraper = JobScraper()
    scraper.perform_searches(["software developer"])
    print(f"Validated links length: {scraper.job_data.final_validated_links_length}")
    print(f"Invalidated links length: {scraper.job_data.final_invalidated_links_length}")
    print(f"Valid links read: {scraper.job_data.final_validated_links_length - scraper.job_data.initial_validated_links_length}")
    print(f"Invalid links read: {scraper.job_data.final_invalidated_links_length - scraper.job_data.initial_invalidated_links_length}")



# This now prints a dictionary where each search term maps to a list of job links
# print(scraper.validated_links)
