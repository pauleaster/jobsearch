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
from .config import DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT


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
        job counts, CSV handlers, lock file handlers, and initial counts.
        Also, initializes the job data by reading existing CSV files.
        """
        # Initialize DB connection
        self.db_handler = DBHandler(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
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

        # Table for jobs
        create_jobs_table_query = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id SERIAL PRIMARY KEY,
            job_number TEXT UNIQUE NOT NULL,
            job_url TEXT UNIQUE NOT NULL,
            title TEXT,
            comments TEXT,
            requirements TEXT,
            follow_up TEXT,
            highlight TEXT,
            applied TEXT,
            contact TEXT,
            application_comments TEXT,
            job_html TEXT,
            valid BOOLEAN DEFAULT FALSE
        );
        """

        # Table for search terms
        create_search_terms_table_query = """
        CREATE TABLE IF NOT EXISTS search_terms (
            term_id SERIAL PRIMARY KEY,
            term_text TEXT UNIQUE NOT NULL
        );
        """

        # Junction table for many-to-many relationship between jobs and search terms
        create_job_search_terms_table_query = """
        CREATE TABLE IF NOT EXISTS job_search_terms (
            job_id INT REFERENCES jobs(job_id),
            term_id INT REFERENCES search_terms(term_id),
            valid BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (job_id, term_id)
        );
        """

        self.db_handler.execute(create_jobs_table_query)
        self.db_handler.execute(create_search_terms_table_query)
        self.db_handler.execute(create_job_search_terms_table_query)


    def get_link_count(self, status: LinkStatus) -> int:
        """
        Return the current count of links for a provided status.
        """
        is_valid = (status == LinkStatus.VALID)
        
        query = """
        SELECT COUNT(DISTINCT job_id) 
        FROM job_search_terms 
        WHERE valid = %s;
        """
        
        result = self.db_handler.fetch(query, (is_valid,))
        
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
        query = """
        SELECT valid FROM jobs WHERE job_number = %s;
        """
        
        result = self.db_handler.fetch(query, (job_number,))
        
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
            job_query = """
            INSERT INTO jobs (job_number, job_url, job_html) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (job_number) 
            DO UPDATE SET 
                job_html = COALESCE(jobs.job_html, EXCLUDED.job_html);  -- Update job_html only if it's NULL in the existing record
            """
            self.db_handler.execute(job_query, (job_number, url, job_html))
        else:
            job_query = """
            INSERT INTO jobs (job_number, job_url) 
            VALUES (%s, %s) 
            ON CONFLICT (job_number) DO NOTHING;  -- Just insert if not exists, don't update
            """
            self.db_handler.execute(job_query, (job_number, url))

        # Insert the search term if it doesn't exist
        search_term_insert_query = """
        INSERT INTO search_terms (term_text) 
        VALUES (%s) 
        ON CONFLICT (term_text)
        DO NOTHING;
        """
        self.db_handler.execute(search_term_insert_query, (search_term,))

        # Fetch the job_id and term_id
        job_id_query = "SELECT job_id FROM jobs WHERE job_number = %s;"
        term_id_query = "SELECT term_id FROM search_terms WHERE term_text = %s;"
        job_id = self.db_handler.fetch(job_id_query, (job_number,))[0][0]
        term_id = self.db_handler.fetch(term_id_query, (search_term,))[0][0]

        # Insert/Update the association between job and search term with validity
        search_term_association_query = """
        INSERT INTO job_search_terms (job_id, term_id, valid) 
        VALUES (%s, %s, %s) 
        ON CONFLICT (job_id, term_id)
        DO UPDATE SET valid = EXCLUDED.valid;
        """
        self.db_handler.execute(search_term_association_query, (job_id, term_id, is_valid))




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
        job_id_query = "SELECT job_id FROM jobs WHERE job_number = %s"
        results = self.db_handler.fetch(job_id_query, (job_number,))
        job_id_result = results[0] if results else None

        # If no job is found with the given job_number, return an empty dictionary
        if not job_id_result:
            return {}

        job_id = job_id_result[0]

        # Query to get the search terms and their validities for the given job_id
        query = """
            SELECT st.term_text, jst.valid
            FROM job_search_terms jst
            JOIN search_terms st ON jst.term_id = st.term_id
            WHERE jst.job_id = %s
        """
        results = self.db_handler.fetch(query, (job_id,))

        # Convert the results into a dictionary: search_term -> validity
        validities = {row[0]: row[1] for row in results}

        return validities
    
    def get_job_html(self, job_number):
        """
        For a given job_number, retrieve the job_html.

        Parameters:
        - job_number (str): The job number to look up.

        Returns:
        - str or None: The job_html if found; otherwise, None.
        """

        # Query to get the job_html for the given job_number
        query = "SELECT job_html FROM jobs WHERE job_number = %s"
        results = self.db_handler.fetch(query, (job_number,))
        job_html_result = results[0] if results else None

        # If no job is found with the given job_number, return None
        if not job_html_result:
            return None

        job_html = job_html_result[0]

        return job_html