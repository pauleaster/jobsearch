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
from datetime import datetime, timedelta
from sqlalchemy import (
    Column, Integer, SmallInteger, String, Text, Boolean, Date, ForeignKey, DateTime
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.engine.url import URL
from .database import engine, SessionLocal

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'
    job_id = Column(Integer, primary_key=True, autoincrement=True)
    job_number = Column(Integer, nullable=False)
    job_url = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    comments = Column(Text, nullable=True)
    requirements = Column(Text, nullable=True)
    follow_up = Column(Text, nullable=True)
    highlight = Column(Text, nullable=True)
    applied = Column(Text, nullable=True)
    contact = Column(Text, nullable=True)
    application_comments = Column(Text, nullable=True)
    job_date = Column(Date, nullable=True)
    salary = Column(Text, nullable=True)
    position = Column(Text, nullable=True)
    advertiser = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    work_type = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)

    job_search_terms = relationship("JobSearchTerm", back_populates="job")

class SearchTerm(Base):
    __tablename__ = 'search_terms'
    term_id = Column(SmallInteger, primary_key=True, autoincrement=True)
    term_text = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)

    job_search_terms = relationship("JobSearchTerm", back_populates="search_term")

class JobSearchTerm(Base):
    __tablename__ = 'job_search_terms'
    job_id = Column(Integer, ForeignKey('jobs.job_id'), primary_key=True)
    term_id = Column(SmallInteger, ForeignKey('search_terms.term_id'), primary_key=True)
    valid = Column(Boolean, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)

    job = relationship("Job", back_populates="job_search_terms")
    search_term = relationship("SearchTerm", back_populates="job_search_terms")


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
        job counts, SQLAlchemy engine/session, and initial counts.
        """
        # Ensure tables are created
        Base.metadata.create_all(engine)
        self.session = SessionLocal()

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



    def get_link_count(self, status: LinkStatus) -> int:
        """
        Return the current count of links for a provided status.
        """
        is_valid = (status == LinkStatus.VALID)
        count = (
            self.session.query(JobSearchTerm)
            .filter(JobSearchTerm.valid == is_valid)
            .distinct(JobSearchTerm.job_id)
            .count()
        )
        return count


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
        job = self.session.query(Job).filter_by(job_number=job_number).first()
        if not job:
            return {LinkStatus.VALID: False, LinkStatus.INVALID: False}
        # Check if there is at least one valid/invalid JobSearchTerm for this job
        valid = self.session.query(JobSearchTerm).filter_by(job_id=job.job_id, valid=True).first() is not None
        invalid = self.session.query(JobSearchTerm).filter_by(job_id=job.job_id, valid=False).first() is not None
        return {LinkStatus.VALID: valid, LinkStatus.INVALID: invalid}

    def add_or_update_link(self, search_term, url, job_number, job_date, status: LinkStatus, salary=None):
        """
        Adds a new job link to the database, categorized by the provided status.
        """
        is_valid = (status == LinkStatus.VALID)

        # Insert or get the job
        job = self.session.query(Job).filter_by(job_number=job_number).first()
        if not job:
            job = Job(job_number=job_number, job_url=url, job_date=job_date, salary=salary)
            self.session.add(job)
            self.session.commit()
        else:
            # Optionally update the job_url and job_date if needed
            job.job_url = url
            job.job_date = job_date
            if salary is not None:
                job.salary = salary
            self.session.commit()

        # Insert or get the search term
        term = self.session.query(SearchTerm).filter_by(term_text=search_term).first()
        if not term:
            term = SearchTerm(term_text=search_term)
            self.session.add(term)
            self.session.commit()

        # Insert or update the association in JobSearchTerm
        job_search_term = self.session.query(JobSearchTerm).filter_by(
            job_id=job.job_id, term_id=term.term_id
        ).first()
        if not job_search_term:
            job_search_term = JobSearchTerm(
                job_id=job.job_id, term_id=term.term_id, valid=is_valid
            )
            self.session.add(job_search_term)
        else:
            job_search_term.valid = is_valid
        self.session.commit()

    def get_search_terms_and_validities(self, job_number):
        """
        For a given job_number, retrieve the associated search terms and their validities.

        Returns:
        - dict: A dictionary where keys are search terms and values are their corresponding validities (as booleans).
        """
        job = self.session.query(Job).filter_by(job_number=job_number).first()
        if not job:
            return {}

        results = (
            self.session.query(SearchTerm.term_text, JobSearchTerm.valid)
            .join(JobSearchTerm, SearchTerm.term_id == JobSearchTerm.term_id)
            .filter(JobSearchTerm.job_id == job.job_id)
            .all()
        )
        validities = {term_text: valid for term_text, valid in results}
        return validities
   
    def calculate_job_date(self, job_age):
        """
        Calculates the age of the job by
        current date - job_age and
        convert to a date only ISO string
        """
        if job_age is None:
            return None
        # calculate the current date
        current_date = datetime.now().date()
        listing_date = current_date - timedelta(days=job_age)
        return listing_date.isoformat()

    def close(self):
        self.session.close()
