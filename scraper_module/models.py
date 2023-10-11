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
import csv
from enum import Enum, auto
from filelock import FileLock
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


class CSVHandler:
    """
    Provides methods for reading and appending to csv files.
    """

    def __init__(self, filename):
        """
        Creates a CSVHandler instance with a filepath
        in the parent directory.
        """
        self.filepath = os.path.join(parent_dir, filename)

    def append_row(self, row):
        """
        Appends a row to the csv file.
        """
        with open(self.filepath, "a", newline="", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(row)

    def read_rows(self):
        """
        Reads the rows from the csv file and returns them as a list.
        """
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as file:
                csv_reader = csv.reader(file)
                return list(csv_reader)
        return []


class LockFileHandler:
    """
    Manages lockfiles for the csv files.
    """

    def __init__(self, lockfilename):
        """
        Creates a LockFileHandler instance with a filepath
        """
        self.lockfilename = os.path.join(current_dir, lockfilename)
        self.lock = FileLock(self.lockfilename)

    def delete(self):
        """
        Deletes the lockfile if it exists.
        """
        if os.path.exists(self.lockfilename):
            os.remove(self.lockfilename)
            print(f"Removed lockfile: {self.lockfilename}")

    def __enter__(self):
        """
        Acquires the lock when entering the context of a `with` statement.

        This allows for safely working with resources, such as files,
        ensuring that only one operation accesses them at a given time.
        """
        self.lock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Releases the lock when exiting the context of a `with` statement.

        This ensures that any other operations waiting for the lock can
        proceed, and the resource (e.g., a file) is freed up for other uses.
        """
        self.lock.release()


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
        self.create_table_if_not_exists()
        print(f"Initial Validated links #{self.get_link_count(LinkStatus.VALID)}")
        print(f"Initial Invalidated links #{self.get_link_count(LinkStatus.INVALID)}")


    def create_table_if_not_exists(self):
        """
        Creates the required table if it does not exist.
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS job_links (
            search_term TEXT NOT NULL,
            job_url TEXT NOT NULL,
            job_number TEXT PRIMARY KEY,
            title TEXT,
            comments TEXT,
            requirements TEXT,
            follow_up TEXT,
            highlight TEXT,
            applied TEXT,
            contact TEXT,
            application_comments TEXT,
            valid BOOLEAN DEFAULT FALSE
        );
        """
        self.db_handler.execute(create_table_query)

    def get_link_count(self, status: LinkStatus) -> int:
        """
        Return the current count of links for a provided status.
        """
        is_valid = (status == LinkStatus.VALID)
        
        query = """
        SELECT COUNT(*) FROM job_links WHERE valid = %s;
        """
        
        result = self.db_handler.fetch(query, (is_valid,))
        
        return result[0][0]


    def get_links_difference(self, status: LinkStatus) -> int:
        """
        Calculates and returns the difference in job link counts from the
        initial count to the current count for a given status.
        """
        return self.get_link_count(status) - self.initial_counts[status]

    def save_link_to_csv(self, search_term, url, status: LinkStatus):
        """
        Saves a job link to its respective CSV file (either validated or
        invalidated) based on its status. Uses a lock to ensure safe
        write operations.
        """

        job_number = url.split("/")[-1]
        row = [search_term, url, job_number]

        with self.lockfile_handlers[status]:
            self.csv_handlers[status].append_row(row)

    def read_csv_files(self):
        """
        Reads job links from their respective CSV files (either validated
        or invalidated) and populates the internal storage structures.
        Uses a lock to ensure safe read operations.
        """
        for status in LinkStatus:
            link_dict = self.links[status]
            job_numbers_set = self.job_numbers[status]

            with self.lockfile_handlers[status]:
                rows = self.csv_handlers[status].read_rows()
                for row in rows:
                    search_term, url, job_number = row
                    if search_term not in link_dict.keys():
                        link_dict[search_term] = []
                    link_dict[search_term].append([url, job_number])
                    job_numbers_set.add(job_number)

    def job_in_links(self, job_number):
        """
        Checks if a job is present in the database and its validity status.
        Returns a dictionary indicating the presence of the job and its validity.
        """
        query = """
        SELECT valid FROM job_links WHERE job_number = %s;
        """
        
        result = self.db_handler.fetch(query, (job_number,))
        
        if not result:
            return {LinkStatus.VALID: False, LinkStatus.INVALID: False}
        
        is_valid = result[0][0]
        return {LinkStatus.VALID: is_valid, LinkStatus.INVALID: not is_valid}


    def add_new_link(self, search_term, url, job_number, status: LinkStatus):
        """
        Adds a new job link to the database, categorized by the provided status.
        """
        is_valid = (status == LinkStatus.VALID)

        # Construct the insertion query
        query = """
        INSERT INTO job_links (search_term, job_url, job_number, valid) 
        VALUES (%s, %s, %s, %s) 
        ON CONFLICT (job_number) 
        DO NOTHING;
        """

        # Execute the query
        self.db_handler.execute(query, (search_term, url, job_number, is_valid))

