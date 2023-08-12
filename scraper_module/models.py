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
        self.links = {LinkStatus.VALID: {}, LinkStatus.INVALID: {}}

        # A dictionary for storing job numbers for each search_term
        self.job_numbers = {LinkStatus.VALID: set(), LinkStatus.INVALID: set()}
        self.csv_files = {
            LinkStatus.VALID: "validated_links.csv",
            LinkStatus.INVALID: "invalidated_links.csv",
        }
        self.csv_handlers = {
            LinkStatus.VALID: CSVHandler(self.csv_files[LinkStatus.VALID]),
            LinkStatus.INVALID: CSVHandler(self.csv_files[LinkStatus.INVALID]),
        }

        self.lockfilenames = {
            LinkStatus.VALID: "validated_lockfile",
            LinkStatus.INVALID: "invalidated_lockfile",
        }

        self.lockfile_handlers = {
            LinkStatus.VALID: LockFileHandler(self.lockfilenames[LinkStatus.VALID]),
            LinkStatus.INVALID: LockFileHandler(self.lockfilenames[LinkStatus.INVALID]),
        }

        # Check for lock files and delete if they exist
        self.delete_lockfiles()
        self.read_csv_files()

        # Store the initial counts
        self.initial_counts = {
            LinkStatus.VALID: self.get_link_count(LinkStatus.VALID),
            LinkStatus.INVALID: self.get_link_count(LinkStatus.INVALID),
        }

        print(f"Initial Validated links #{self.get_link_count(LinkStatus.VALID)}")
        print(f"Initial Invalidated links #{self.get_link_count(LinkStatus.INVALID)}")

    def delete_lockfiles(self):
        """Deletes the lockfiles."""
        for lockfile_handler in self.lockfile_handlers.values():
            lockfile_handler.delete()

    def get_link_count(self, status: LinkStatus) -> int:
        """Return the current count of links for a provided status."""
        return sum(len(links) for links in self.links[status].values())

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

    def job_in_links(self, job):
        """
        Checks if a job is present in either the validated or invalidated links set.
        Returns a dictionary indicating the presence of the job in each set.
        """
        results = {}
        for status in LinkStatus:
            results[status] = job in self.job_numbers[status]
        return results

    def add_new_link(self, search_term, url, job_number, status: LinkStatus):
        """
        Adds a new job link to the internal storage, categorized by the provided status.
        Updates both the link dictionary and job number set.
        """
        if search_term not in self.links[status]:
            self.links[status][search_term] = []
        self.links[status][search_term].append([url, job_number])
        self.job_numbers[status].add(job_number)
