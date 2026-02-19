import pandas as pd
from scraper_module.models import JobData, Job, JobSearchTerm
from scraper_module.scraper import JobScraper
from datetime import datetime

def extract_position(soup):
    tag = soup.find("h1", {"data-automation": "job-detail-title"})
    return tag.get_text(strip=True) if tag else None

def extract_advertiser(soup):
    tag = soup.find("span", {"data-automation": "advertiser-name"})
    if tag:
        return tag.contents[0].strip() if tag.contents else tag.get_text(strip=True)
    return None

def extract_location(soup):
    tag = soup.find("span", {"data-automation": "job-detail-location"})
    if tag:
        a_tag = tag.find("a")
        return a_tag.get_text(strip=True) if a_tag else tag.get_text(strip=True)
    return None

def extract_work_type(soup):
    tag = soup.find("span", {"data-automation": "job-detail-work-type"})
    if tag:
        a_tag = tag.find("a")
        return a_tag.get_text(strip=True) if a_tag else tag.get_text(strip=True)
    return None

def main():
    import time
    job_data = JobData()
    session = job_data.session
    scraper = JobScraper(load_network_handler=True)

    valid_job_ids = (
        session.query(JobSearchTerm.job_id)
        .filter(JobSearchTerm.valid == True)
        .distinct()
        .all()
    )
    valid_job_ids = [jid[0] for jid in valid_job_ids]

    jobs = session.query(Job).filter(Job.job_id.in_(valid_job_ids)).all()
    total_jobs = len(jobs)
    print(f"Found {total_jobs} jobs with at least one valid search term.")

    updated_count = 0
    start_time = time.time()
    for idx, job in enumerate(jobs, 1):
        percent = (idx / total_jobs) * 100
        elapsed = time.time() - start_time
        if percent > 0:
            est_total = elapsed / (percent / 100)
            est_remaining = est_total - elapsed
            eta = datetime.now() + pd.to_timedelta(est_remaining, unit='s')
            eta_str = eta.strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{idx}/{total_jobs}] ({percent:.1f}%) ETA: {eta_str}\nProcessing job_number={job.job_number} url={job.job_url}")
        else:
            print(f"[{idx}/{total_jobs}] ({percent:.1f}%) Processing job_number={job.job_number} url={job.job_url}")

        soup = scraper.network_handler.get_soup(job.job_url)
        if soup:
            position = extract_position(soup)
            advertiser = extract_advertiser(soup)
            location = extract_location(soup)
            work_type = extract_work_type(soup)

            job.position = position if position else job.position
            job.advertiser = advertiser if advertiser else job.advertiser
            job.location = location if location else job.location
            job.work_type = work_type if work_type else job.work_type

            job.updated_at = datetime.now()

            session.commit()
            updated_count += 1
            print(f"  -> Fields updated: position={position}, advertiser={advertiser}, location={location}, work_type={work_type}")
        else:
            print("  -> Failed to load job page.")

    print(f"Updated main fields for {updated_count} jobs.")

    job_data.close()
    scraper.network_handler.close()

if __name__ == "__main__":
    main()