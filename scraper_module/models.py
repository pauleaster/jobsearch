"""
models.py
---------

This module defines structures and utilities for handling job-related data:

- `LinkStatus`: Enum representing job link validity.
- `CSVHandler`: Utility for reading/writing to CSV files.
- `LockFileHandler`: Manages concurrency using lock files for file access.
- `JobData`: Manages job data, including links' validity, and tracks counts.

The module also sets up paths for file management.

Examples:
    >>> job_data = JobData()
    >>> status = job_data.job_in_links("job-id")
    >>> if not status[LinkStatus.VALID]:
    ...     job_data.add_new_link("term", "https://example.com/job-id", "job-id",
    ...                           LinkStatus.VALID)

Note: Ensure lockfiles are managed properly, especially in multi-threaded scenarios.
"""



import os
from enum import Enum, auto
from .db_handler import DBHandler
from .config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, AUTH_METHOD
from .queries import SQLQueries


current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)


class LinkStatus(Enum):
    """
    Flag to indicate whether the links are valid or not.
    Used as a key in the links dictionary.
    """

    VALID = auto()
    INVALID = auto()

class JobData:
    """
    Handles the storage, management, and manipulation of job-related data
    including their links and statuses (valid or invalid).
    """

    def __init__(self):
        """
        Initializes an instance of JobData with storage structures for job links,
        job counts, SQL Server database handlers, and initial counts.
        Also, initializes the job data by reading existing CSV files.
        """
        # Initialize DB connection
        self.db_handler = DBHandler(dbname=DB_NAME, auth_method=AUTH_METHOD, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
        self.db_handler.connect()

        # Ensure the required table exists
        self.create_tables_if_not_exists()

        # Store the initial counts
        self.initial_counts = {
            LinkStatus.VALID: self.get_link_count(LinkStatus.VALID),
            LinkStatus.INVALID: self.get_link_count(LinkStatus.INVALID),
        }

        print(f"Initial Validated links #{self.get_link_count(LinkStatus.VALID)}")
        print(f"Initial Invalidated links #{self.get_link_count(LinkStatus.INVALID)}")

    def extract_job_number_from_url(self, url):
        """
        Extracts the job number from the provided URL by looking for the characters
        after the last forward slash.
        """
        return url.split("/")[-1]



    def create_tables_if_not_exists(self):
        """
        Creates the required tables if they do not exist.
        """
        self.db_handler.execute(SQLQueries.CREATE_JOBS_TABLE_QUERY)
        self.db_handler.execute(SQLQueries.CREATE_SEARCH_TERMS_TABLE_QUERY)
        self.db_handler.execute(SQLQueries.CREATE_JOB_SEARCH_TERMS_TABLE_QUERY)


    def get_link_count(self, status: LinkStatus) -> int:
        """
        Return the current count of links for a provided status.
        """
        is_valid = (status == LinkStatus.VALID)
        
        result = self.db_handler.fetch(SQLQueries.GET_DISTINCT_JOBS_QUERY, (is_valid,))
        
        return result[0][0]


    def get_links_difference(self, status: LinkStatus) -> int:
        """
        Calculates and returns the difference in job link counts from the
        initial count to the current count for a given status.
        """
        return self.get_link_count(status) - self.initial_counts[status]

    def job_in_links(self, job_number):
        """
        Checks if a job is present in the database and its validity status.
        Returns a dictionary indicating the presence of the job and its validity.
        """
        
        result = self.db_handler.fetch(SQLQueries.JOB_IN_LINKS_QUERY, (job_number,))
        
        if not result:
            return {LinkStatus.VALID: False, LinkStatus.INVALID: False}
        
        is_valid = result[0][0]
        return {LinkStatus.VALID: is_valid, LinkStatus.INVALID: not is_valid}


    def add_new_link(self, search_term, url, job_number, status: LinkStatus, job_html=None):
        """
        Adds a new job link to the database, categorized by the provided status.
        """
        is_valid = (status == LinkStatus.VALID)

        # Insert/Update the job details
        if is_valid and job_html:
            self.db_handler.execute(SQLQueries.UPSERT_JOB_DETAILS_WITH_CONDITIONAL_HTML_UPDATE_QUERY, (job_number, job_html, job_number, job_number, url, job_html))
        else:
            self.db_handler.execute(SQLQueries.INSERT_JOB_IF_NOT_EXISTS_QUERY, (job_number, job_number, url))


        # Insert the search term if it doesn't exist
        
        self.db_handler.execute(SQLQueries.SEARCH_TERM_INSERT_QUERY, (search_term, search_term))


        # Fetch the job_id and term_id
        
        job_id = self.db_handler.fetch(SQLQueries.JOB_ID_QUERY, (job_number,))[0][0]
        term_id = self.db_handler.fetch(SQLQueries.TERM_ID_QUERY, (search_term,))[0][0]

        # Insert/Update the association between job and search term with validity
        
        self.db_handler.execute(SQLQueries.UPSERT_JOB_SEARCH_TERM_VALIDITY, (job_id, term_id, is_valid, is_valid))





    def save_link(self, search_term, url, link_status):
        """
        Saves the provided link to the database, categorized by the provided status.
        """
        job_number = self.extract_job_number_from_url(url)
        self.add_new_link(search_term, url, job_number, link_status)


    def get_search_terms_and_validities(self, job_number):
        """
        For a given job_number, retrieve the associated search terms and their validities.

        Parameters:
        - job_number (str): The job number to look up.

        Returns:
        - dict: A dictionary where keys are search terms and values are their corresponding validities (as booleans).
        """

        # Query to get the job_id for the given job_number
        
        results = self.db_handler.fetch(SQLQueries.JOB_ID_QUERY, (job_number,))
        job_id_result = results[0] if results else None

        # If no job is found with the given job_number, return an empty dictionary
        if not job_id_result:
            return {}

        job_id = job_id_result[0]

        # Query to get the search terms and their validities for the given job_id
        
        results = self.db_handler.fetch(SQLQueries.GET_SEARCH_TERM_VALIDITIES_FROM_JOB, (job_id,))

        # Convert the results into a dictionary: search_term -> validity
        validities = {row[0]: row[1] for row in results}

        return validities
    
    def get_job_html(self, job_number):
        """
        This function has been depricated.
        It returns None only
        Parameters:
        - job_number (str): The job number to look up.

        Returns:
        - None: This function has been depricated.
        """
        return None