import os
import time
from datetime import datetime, timedelta

import pandas as pd

from scraper_module.database import commit_with_retry
from scraper_module.delays import DelaySettings
from scraper_module.models import Job, JobSearchTerm
from scraper_module.scraper import JobScraper

EXPIRY_DAYS = 28
EXPIRY_CHECK_DELAY = 1  # seconds between each job URL check
HANDLER_BATCH_SIZE = 10  # jobs per handler before switching
LAST_RUN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".last_expiry_run"
)


def mark_expired_jobs(scraper: JobScraper):
    """
    Checks valid jobs older than EXPIRY_DAYS (by job_date), plus jobs with no
    job_date, and marks them as expired if the job site shows "This job is no longer advertised".
    Alternates between network handlers in batches of HANDLER_BATCH_SIZE.
    Uses the scraper's existing network handlers and db session.
    """
    # Check if last run was recent enough
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE) as f:
            last_run = datetime.fromisoformat(f.read().strip())
        hours_since = (datetime.now() - last_run).total_seconds() / 3600
        print(f"Last expiry check was {hours_since:.1f} hours ago.")
        if hours_since < DelaySettings.EXPIRED_RESET_TIME_HOURS.value:
            print(
                f"Skipping expiry check (last run {hours_since:.1f}h ago, threshold is {DelaySettings.EXPIRED_RESET_TIME_HOURS.value}h)"
            )
            return

    session = scraper.job_data.session
    handlers = scraper.network_handlers

    cutoff = datetime.now().date() - timedelta(days=EXPIRY_DAYS)

    job_ids = (
        session.query(JobSearchTerm.job_id)
        .join(Job, Job.job_id == JobSearchTerm.job_id)
        .filter(JobSearchTerm.valid.is_(True))
        .filter((Job.expired.is_(None)) | (Job.expired.is_(False)))
        .filter((Job.job_date.is_(None)) | (Job.job_date < cutoff))
        .distinct()
        .all()
    )
    job_ids = [jid[0] for jid in job_ids]

    jobs: list[Job] = session.query(Job).filter(Job.job_id.in_(job_ids)).all()
    total_jobs = len(jobs)

    print(f"\nChecking {total_jobs} jobs for expiry...")
    expired_count = 0
    checked_count = 0
    start_time = time.time()

    try:
        for i, job in enumerate(jobs):
            handler = handlers[(i // HANDLER_BATCH_SIZE) % len(handlers)]

            if i == 0 or i % 20 == 0:
                elapsed = time.time() - start_time
                if i > 0:
                    avg = elapsed / i
                    remaining = avg * (total_jobs - i)
                    eta = datetime.now() + pd.to_timedelta(remaining, unit="s")
                    eta_str = eta.strftime("%H:%M:%S")
                else:
                    eta_str = "calculating..."
                print(f"\n[{i + 1}/{total_jobs}] ETA: {eta_str}", flush=True)

            soup = handler.get_soup(job.job_url)
            if soup is None:
                print("?", end="", flush=True)
            else:
                page_text = (
                    soup.get_text(separator=" ", strip=True)
                    .lower()
                    .replace("\u2019", "'")
                )
                if (
                    "this job is no longer advertised" in page_text
                    or "we couldn't find that page" in page_text
                ):
                    job.expired = True
                    job.updated_at = datetime.now()
                    expired_count += 1
                    print("E", end="", flush=True)
                    commit_with_retry(session)
                else:
                    job.expired = False
                    job.updated_at = datetime.now()
                    print(".", end="", flush=True)
                    commit_with_retry(session)

            checked_count += 1
            # time.sleep(EXPIRY_CHECK_DELAY)

    except KeyboardInterrupt:
        print("\nExpiry check interrupted by user.")

    finally:
        print(
            f"\nChecked {checked_count}/{total_jobs} jobs. Marked {expired_count} as expired."
        )
        scraper.refresh_all_handlers()
        # At the end of the finally block, record the run time
        with open(LAST_RUN_FILE, "w") as f:
            f.write(datetime.now().isoformat())
