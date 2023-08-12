import time

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException
)
import requests
from bs4 import BeautifulSoup

from .delays import DelaySettings


class NetworkHandler:
    """
    Handles web access using delays from DelaySettings.
    """

    def __init__(self, url):
        self.successive_url_read_delay = DelaySettings.SUCCESSIVE_URL_READ_DELAY.value
        self.last_request_time = 0
        self.time_since_last_request = 0
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, self.successive_url_read_delay)
        print(f"Opening {url}")
        self.driver.get(url)

    def selenium_interaction_delay(self):
        """Handles the delay for Selenium interactions to ensure the browser has time to react."""
        time.sleep(DelaySettings.SELENIUM_INTERACTION_DELAY.value)

    def find_elements(self, by, value):  # pylint: disable=invalid-name
        elements = self.driver.find_elements(by, value)
        self.selenium_interaction_delay()
        return elements

    def find_job_links(self):
        """Find and return job links on the current page."""
        xpath_expression = '//a[contains(@href, "/job/")]'
        return self.find_elements(By.XPATH, xpath_expression)

    def initiate_search(self, search_term):
        search_field = self.driver.find_element(By.ID, "keywords-input")
        search_field.send_keys(Keys.CONTROL + "a")
        search_field.send_keys(Keys.DELETE)
        search_field.send_keys(search_term)
        search_field.send_keys(Keys.RETURN)
        self.selenium_interaction_delay()  # Add the delay after initiating the search

    def click_next_button(self):
        try:
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
            return True  # Successfully clicked the button

        except (
            ElementClickInterceptedException,
            NoSuchElementException,
            TimeoutException
        ):
            return (
                False  # Failed to click the button because of one of these exceptions
            )

    def handle_successive_url_read_delay(self):
        """
        Handles the delay between successive URL reads to adhere to a specific delay setting.

        1. Calculates the time since the last request.
        2. If this time is less than the configured SUCCESSIVE_URL_READ_DELAY,
            sleeps for the remaining time.
        3. Resets the last request time to the current time.
        """
        self.time_since_last_request = time.time() - self.last_request_time
        if self.time_since_last_request < DelaySettings.SUCCESSIVE_URL_READ_DELAY.value:
            time.sleep(
                DelaySettings.SUCCESSIVE_URL_READ_DELAY.value
                - self.time_since_last_request
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
        for _ in range(DelaySettings.NUM_RETRIES.value):
            try:
                request = requests.get(url, timeout=DelaySettings.REQUEST_TIMEOUT.value)
                self.last_request_time = time.time()
                return request
            except requests.RequestException as exception:
                last_exception = exception
                print("E", end="")
                time.sleep(DelaySettings.REQUEST_EXCEPTION_DELAY.value)
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
