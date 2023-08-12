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
    def __init__(self, filename):
        self.filepath = os.path.join(parent_dir, filename)

    def append_row(self, row):
        with open(self.filepath, "a", newline="", encoding="utf-8") as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(row)

    def read_rows(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, "r", encoding="utf-8") as file:
                csv_reader = csv.reader(file)
                return list(csv_reader)
        return []

class LockFileHandler:
    def __init__(self, lockfilename):
        self.lockfilename = os.path.join(current_dir, lockfilename)
        self.lock = FileLock(self.lockfilename)

    def delete(self):
        if os.path.exists(self.lockfilename):
            os.remove(self.lockfilename)
            print(f"Removed lockfile: {self.lockfilename}")

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()

class JobData:
    def __init__(self):
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

        self.locks = {
            LinkStatus.VALID: FileLock(self.lockfilenames[LinkStatus.VALID]),
            LinkStatus.INVALID: FileLock(self.lockfilenames[LinkStatus.INVALID]),
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
        """Return the current count of links for a specific status."""
        return sum(len(links) for links in self.links[status].values())

    def get_links_difference(self, status: LinkStatus) -> int:
        """
        Return the difference between initial and current count of links
        for a specific status."""
        return self.get_link_count(status) - self.initial_counts[status]

    def save_link_to_csv(self, search_term, url, status: LinkStatus):
        """
        Saves the current link to validated_links.csv
        or invalidated_links.csv depending on whether the link is valid or not
        and closes the file.
        """

        job_number = url.split("/")[-1]
        row = [search_term, url, job_number]

        with self.lockfile_handlers[status]:
            self.csv_handlers[status].append_row(row)

    def read_csv_files(self):
        """
        Reads the validated_links.csv and invalidated_links.csv files
        and recreates the validated_links and invalidated_links dictionaries
        from the data in the files and then closes the files.
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
        Returns a dictionary of booleans indicating whether the job is present in
        the validated_links or invalidated_links dictionaries for any search_term.
        The dictionary keys are LinkStatus.VALID and LinkStatus.INVALID.
        """
        results = {}
        for status in LinkStatus:
            results[status] = job in self.job_numbers[status]
        return results

    def add_new_link(self, search_term, url, job_number, status: LinkStatus):
        """
        Adds a new link to the links dictionary depending on the link's status.
        """
        if search_term not in self.links[status]:
            self.links[status][search_term] = []
        self.links[status][search_term].append([url, job_number])
        self.job_numbers[status].add(job_number)
