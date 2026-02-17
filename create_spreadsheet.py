import pandas as pd
from scraper_module.models import JobData, SearchTerm, Job, JobSearchTerm

def main():
    job_data = JobData()
    session = job_data.session

    # Get all search terms
    search_terms = session.query(SearchTerm).order_by(SearchTerm.term_id).all()
    search_term_texts = [term.term_text for term in search_terms]
    search_term_ids = [term.term_id for term in search_terms]

    # Get all jobs
    jobs = session.query(Job).all()

    rows = []
    for job in jobs:
        row = {
            "job_id": job.job_id,
            "job_number": job.job_number,
            "job_url": job.job_url,
            "title": job.title,
            "comments": job.comments,
            "requirements": job.requirements,
            "follow_up": job.follow_up,
            "highlight": job.highlight,
            "applied": job.applied,
            "contact": job.contact,
            "application_comments": job.application_comments,
            "job_date": job.job_date,
        }
        valid_count = 0
        # Add a column for each search term
        for term_id, term_text in zip(search_term_ids, search_term_texts):
            valid = (
                session.query(JobSearchTerm)
                .filter_by(job_id=job.job_id, term_id=term_id, valid=True)
                .first()
            )
            is_valid = 1 if valid else 0
            row[term_text] = is_valid
            valid_count += is_valid
        row["valid_term_count"] = valid_count
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_excel("jobsearch_export.xlsx", index=False)
    print("Spreadsheet created: jobsearch_export.xlsx")

if __name__ == "__main__":
    main()