import pandas as pd
from sqlalchemy.inspection import inspect
from scraper_module.models import JobData, SearchTerm, Job, JobSearchTerm
from datetime import datetime

def main():
    job_data = JobData()
    session = job_data.session

    # Get all search terms
    search_terms = session.query(SearchTerm).order_by(SearchTerm.term_id).all()
    search_term_texts = [term.term_text for term in search_terms]
    search_term_ids = [term.term_id for term in search_terms]

    # Dynamically get all columns from the Job model/table
    job_columns = [col.key for col in inspect(Job).mapper.column_attrs]

    # Get all jobs
    jobs = session.query(Job).all()

    rows = []
    for job in jobs:
        # Dynamically populate all columns from the Job object
        row = {col: getattr(job, col) for col in job_columns}
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
    timestamp = datetime.now().strftime("_%Y%m%d%H%M%S")
    filename = f"jobsearch_export{timestamp}.xlsx"

    # Add a helper column for salary presence (1 if salary present, else 0)
    df["_has_salary"] = df["salary"].notnull().astype(int) if "salary" in df.columns else 0

    # Native sorting: valid_term_count DESC, has_salary DESC, 'python' DESC, updated_at DESC
    sort_fields = ["valid_term_count", "_has_salary"]
    ascending = [False, False]

    if "python" in df.columns:
        sort_fields.append("python")
        ascending.append(False)
    if "updated_at" in df.columns:
        sort_fields.append("updated_at")
        ascending.append(False)

    df = df.sort_values(by=sort_fields, ascending=ascending)
    df = df.drop(columns=["_has_salary"])

    df.to_excel(filename, index=False)
    print(f"Spreadsheet created: {filename}")

if __name__ == "__main__":
    main()