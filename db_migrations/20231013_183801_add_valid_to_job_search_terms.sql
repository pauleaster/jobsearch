-- Migrate valid status from jobs to job_search_terms
ALTER TABLE job_search_terms ADD COLUMN valid BOOLEAN DEFAULT FALSE;

UPDATE job_search_terms jst
SET valid = j.valid
FROM jobs j
WHERE jst.job_id = j.job_id;

-- Drop valid column from jobs after migration
ALTER TABLE jobs DROP COLUMN valid;
