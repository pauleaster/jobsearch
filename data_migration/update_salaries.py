import pandas as pd
from scraper_module.models import JobData, Job, JobSearchTerm
from scraper_module.scraper import JobScraper

def main():
    job_data = JobData()
    session = job_data.session
    scraper = JobScraper(load_network_handler=True)

    # Query all jobs where at least one search term is valid
    valid_job_ids = (
        session.query(JobSearchTerm.job_id)
        .filter(JobSearchTerm.valid == True)
        .distinct()
        .all()
    )
    valid_job_ids = [jid[0] for jid in valid_job_ids]

    jobs = session.query(Job).filter(Job.job_id.in_(valid_job_ids)).all()
    print(f"Found {len(jobs)} jobs with at least one valid search term.")

    updated_count = 0
    for job in jobs:
        if job.salary:  # Skip if salary already present
            continue
        print(f"Processing job_number={job.job_number} url={job.job_url}")
        soup = scraper.network_handler.get_soup(job.job_url)
        if soup:
            salary = scraper.extract_salary(soup)
            if salary:
                job.salary = salary
                session.commit()
                updated_count += 1
                print(f"  -> Salary updated: {salary}")
            else:
                print("  -> Salary not found.")
        else:
            print("  -> Failed to load job page.")

    print(f"Updated salary for {updated_count} jobs.")

    # Clean up
    job_data.close()
    scraper.network_handler.close()

if __name__ == "__main__":
    main()