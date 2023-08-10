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
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, self.successive_url_read_delay)
        print(f"Opening {url}")
        self.driver.get(url)

    def find_elements(self, by, value):
        return self.driver.find_elements(by, value)

    def find_element(self, by, value):
        return self.driver.find_element(by, value)

    def click_next_button(self):
        next_button = self.wait.until(EC.presence_of_element_located(
            (By.XPATH, '//a[starts-with(@data-automation, "page-") and @aria-label="Next"]')))
        next_button.click()

    def get_request(self, url):
        last_exception = None
        for _ in range(DelaySettings.NUM_RETRIES):
            try:
                return requests.get(url)
            except requests.RequestException as e:
                last_exception = e
                print('E', end = '')
                time.sleep(DelaySettings.REQUEST_EXCEPTION_DELAY)
        raise last_exception


    def close(self):
        self.driver.quit()


class JobScraper:
    def __init__(self):
        self.validated_links = {}
        self.invalidated_links = {}
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.successive_url_read_delay = 20 # seconds
        self.url = "https://www.seek.com.au/jobs/in-All-Melbourne-VIC"
        self.network_handler = NetworkHandler(self.url)
        self.validated_csv_file = 'validated_links.csv'
        self.invalidated_csv_file = 'invalidated_links.csv'
        self.validated_lockfilename = "validated_lockfile"
        self.invalidated_lockfilename = "invalidated_lockfile"
        # Check for lock files and delete if they exist
        for lockfile in [self.validated_lockfilename, self.invalidated_lockfilename]:
            if os.path.exists(lockfile):
                os.remove(lockfile)
                print(
                    f"Removed lockfile: {lockfile} due to potential previous error state.")

        self.validated_lock = FileLock(self.validated_lockfilename)
        self.invalidated_lock = FileLock(self.invalidated_lockfilename)

        self.read_csv_files()

        self.initial_validated_links_length = len(self.validated_links)
        self.initial_invalidated_links_length = len(self.invalidated_links)
        print(f"len validated_links: {self.initial_validated_links_length}")
        print(f"len invalidated_links: {self.initial_invalidated_links_length}")

    # def recreate_csv_files(self)
    # Reads the validated_links.csv and invalidated_links.csv files
    # and recreates the validated_links and invalidated_links dictionaries
    # from the data in the files and then closes the files

    def read_csv_files(self):
        with self.validated_lock:
            if os.path.exists(self.validated_csv_file):
                with open(self.validated_csv_file, 'r') as file:
                    csv_reader = csv.reader(file)
                    for row in csv_reader:
                        search_term, link,job_number = row
                        if search_term not in self.validated_links.keys():
                            self.validated_links[search_term] = []
                        self.validated_links[search_term].append([link, job_number])

        with self.invalidated_lock:
            if os.path.exists(self.invalidated_csv_file):
                with open(self.invalidated_csv_file, 'r') as file:
                    csv_reader = csv.reader(file)
                    for row in csv_reader:
                        search_term, link, job_number = row
                        if search_term not in self.invalidated_links.keys():
                            self.invalidated_links[search_term] = []
                        self.invalidated_links[search_term].append([link, job_number])

    # def save_links_to_csv(self)
    # Saves the current link to validated_links.csv
    # or invalidated_links.csv depending on whether the link is valid or not
    # and closes the file

    def save_link_to_csv(self, search_term, url, valid):

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

    def is_valid_link(self, search_term, url):

        current_time = time.time()
        self.time_since_last_request = current_time - self.last_request_time
        if self.time_since_last_request < self.successive_url_read_delay:
            # sleep for the remaining time
            time.sleep(self.successive_url_read_delay -
                       self.time_since_last_request)
        response = self.network_handler.get_request(url)
        if response.status_code == 200:
            # print(f"Request successful for {url}")
            soup = BeautifulSoup(response.text, 'html.parser')
            self.last_request_time = time.time()
            if soup:
                soup_str = str(soup).lower()
                valid = search_term.lower() in soup_str
            else:
                valid = False  # empty soup
        else:  # request failed
            valid = False
        self.last_request_time = time.time()
        self.save_link_to_csv(search_term, url, valid)
        return valid
    
    def job_in_links(self, job, search_term):
        # get all the job numbers removing the urls
        # from the validated_links[search_term] and invalidated_links dictionaries[search_term]
        # and return a tuple whether the job is present in (validated_links, invalidated_links)
        validated_jobs =[]
        invalidated_jobs = []
        for (_, job_number) in self.validated_links[search_term]:
            validated_jobs.append(job_number)
        for (_, job_number) in self.invalidated_links[search_term]:
            invalidated_jobs.append(job_number)
        return (job in validated_jobs, job in invalidated_jobs)

    def perform_searches(self, search_terms):
        try:
            for search_term in search_terms:
                print(f"Processing search {search_term}")
                # initialise an empty list if key does not exist
                if search_term not in self.validated_links:
                    self.validated_links[search_term] = []
                if search_term not in self.invalidated_links:
                    self.invalidated_links[search_term] = []
                # enter search term and submit
                search_field = self.network_handler.find_element(By.ID, "keywords-input")
                # or Keys.COMMAND + 'a' on Mac
                search_field.send_keys(Keys.CONTROL + 'a')
                search_field.send_keys(Keys.DELETE)
                search_field.send_keys(search_term)
                search_field.send_keys(Keys.RETURN)
                page_number = 1
                print(f"page {page_number}")
                while True:
                    try:
                        # Code to scrape job links from the current page...
                        job_links = self.network_handler.find_elements(By.XPATH, '//a[contains(@href, "/job/")]')
                        time.sleep(DelaySettings.SELENIUM_INTERACTION_DELAY)
                        for link in job_links:
                            url = link.get_attribute('href').split("?")[0]
                            job_number = url.split("/")[-1]
                            (validated_job, invalidated_job) = self.job_in_links(job_number, search_term)

                            if validated_job :
                                print("X",end="")
                                continue
                            elif invalidated_job:
                                print("x",end="")
                                continue
                            if self.is_valid_link(search_term, url):
                                self.validated_links[search_term].append([url, job_number])
                                print("V", end="")
                            else:
                                self.invalidated_links[search_term].append([url, job_number])
                                print("I", end="")
                        print()
                        # Try to find the "Next" button and click it
                        self.network_handler.click_next_button()
                        page_number += 1
                        print(f"page {page_number}")
                        # You might need to add a delay here to wait for the next page to load
                        time.sleep(DelaySettings.SELENIUM_INTERACTION_DELAY)
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
        self.final_validated_links_length = len(self.validated_links)
        self.final_invalidated_links_length = len(self.invalidated_links)


# Usage:
scraper = JobScraper()
scraper.perform_searches(["software engineer"])
print(f"Validated links length: {scraper.final_validated_links_length}")
print(f"Invalidated links length: {scraper.final_invalidated_links_length}")
print(f"Valid links read: {scraper.final_validated_links_length - scraper.initial_validated_links_length}")
print(f"Invalid links read: {scraper.final_invalidated_links_length - scraper.initial_invalidated_links_length}")


# This now prints a dictionary where each search term maps to a list of job links
# print(scraper.validated_links)
