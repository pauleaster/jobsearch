import time
from datetime import datetime, timedelta
from scraper_module.models import Job, JobSearchTerm
import pandas as pd


EXPIRY_DAYS = 28
EXPIRY_CHECK_DELAY = 1  # seconds between each job URL check
HANDLER_BATCH_SIZE = 10  # jobs per handler before switching


def mark_expired_jobs(scraper):
    """
    Checks valid jobs older than EXPIRY_DAYS (by job_date), plus jobs with no
    job_date, and marks them as expired if Seek shows "This job is no longer advertised".
    Alternates between network handlers in batches of HANDLER_BATCH_SIZE.
    Uses the scraper's existing network handlers and db session.
    """
    session = scraper.job_data.session
    handlers = scraper.network_handlers

    cutoff = datetime.now().date() - timedelta(days=EXPIRY_DAYS)

    job_ids = (
        session.query(JobSearchTerm.job_id)
        .join(Job, Job.job_id == JobSearchTerm.job_id)
        .filter(JobSearchTerm.valid == True)
        .filter((Job.expired == None) | (Job.expired == False))
        .filter((Job.job_date == None) | (Job.job_date < cutoff))
        .distinct()
        .all()
    )
    job_ids = [jid[0] for jid in job_ids]

    jobs = session.query(Job).filter(Job.job_id.in_(job_ids)).all()
    total_jobs = len(jobs)

    print(f"\nChecking {total_jobs} jobs for expiry...")
    expired_count = 0
    start_time = time.time()

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
            print(f"\n[{i+1}/{total_jobs}] ETA: {eta_str}", flush=True)

        soup = handler.get_soup(job.job_url)
        if soup is None:
            print("?", end="", flush=True)
        page_text = soup.get_text(separator=" ", strip=True).lower().replace("\u2019", "'")
        if (
            "this job is no longer advertised" in page_text
            or "we couldn't find that page" in page_text
        ):
            job.expired = True
            job.updated_at = datetime.now()
            expired_count += 1
            print("E", end="", flush=True)
            session.commit()
        else:
            job.expired = False
            job.updated_at = datetime.now()
            print(".", end="", flush=True)
            session.commit()

        # time.sleep(EXPIRY_CHECK_DELAY)

    print(f"\nMarked {expired_count} jobs as expired.")
    scraper.refresh_all_handlers()
