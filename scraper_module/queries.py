
class SQLQueries:

    # Table for jobs
    CREATE_JOBS_TABLE_QUERY = """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = N'jobs' AND type = 'U')
            BEGIN
            CREATE TABLE dbo.jobs (
                job_id INT PRIMARY KEY,
                job_number INT NOT NULL,
                job_url TEXT NOT NULL,
                title TEXT NULL,
                comments TEXT NULL,
                requirements TEXT NULL,
                follow_up TEXT NULL,
                highlight TEXT NULL,
                applied TEXT NULL,
                contact TEXT NULL,
                application_comments TEXT NULL,
                job_html NVARCHAR(MAX) NULL
            );
            END
            """

    # Table for search terms
    CREATE_SEARCH_TERMS_TABLE_QUERY = """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = N'search_terms' AND type = 'U')
            BEGIN
            CREATE TABLE dbo.search_terms (
                term_id SMALLINT PRIMARY KEY,
                term_text NVARCHAR(MAX) NOT NULL
            );
            END
            """


    # Junction table for many-to-many relationship between jobs and search terms
    CREATE_JOB_SEARCH_TERMS_TABLE_QUERY = """
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = N'job_search_terms' AND type = 'U')
            BEGIN
            CREATE TABLE dbo.job_search_terms (
                job_id INT NOT NULL,
                term_id SMALLINT NOT NULL,
                valid BIT NOT NULL,
                PRIMARY KEY (job_id, term_id),
                FOREIGN KEY (job_id) REFERENCES dbo.jobs(job_id),
                FOREIGN KEY (term_id) REFERENCES dbo.search_terms(term_id)
            );
            END
            """

    GET_DISTINCT_JOBS_QUERY = """
            SELECT COUNT(DISTINCT job_id) 
            FROM job_search_terms 
            WHERE valid = ?;
            """

    JOB_IN_LINKS_QUERY = """
            SELECT valid FROM jobs WHERE job_number = ?;
            """

    UPSERT_JOB_DETAILS_WITH_CONDITIONAL_HTML_UPDATE_QUERY = """
            IF EXISTS (SELECT 1 FROM jobs WHERE job_number = ?)
            BEGIN
                -- Update job_html only if it's NULL in the existing record
                UPDATE jobs 
                SET job_html = COALESCE(job_html, ?)
                WHERE job_number = ?
            END
            ELSE
            BEGIN
                INSERT INTO jobs (job_number, job_url, job_html) 
                VALUES (?, ?, ?);
            END
            """

    INSERT_JOB_IF_NOT_EXISTS_QUERY = """
            IF NOT EXISTS (SELECT 1 FROM jobs WHERE job_number = ?)
            BEGIN
                INSERT INTO jobs (job_number, job_url) 
                VALUES (?, ?);
            END
            """

    SEARCH_TERM_INSERT_QUERY = """
            IF NOT EXISTS (SELECT 1 FROM search_terms WHERE term_text = ?)
            BEGIN
                INSERT INTO search_terms (term_text) 
                VALUES (?);
            END
            """

    JOB_ID_QUERY = "SELECT job_id FROM jobs WHERE job_number = ?;"


    TERM_ID_QUERY = "SELECT term_id FROM search_terms WHERE term_text = ?;"

    UPSERT_JOB_SEARCH_TERM_VALIDITY = """
            MERGE INTO job_search_terms AS target
            USING (SELECT ? AS job_id, ? AS term_id) AS source
            ON target.job_id = source.job_id AND target.term_id = source.term_id
            WHEN MATCHED THEN 
                UPDATE SET valid = ?
            WHEN NOT MATCHED THEN 
                INSERT (job_id, term_id, valid) VALUES (source.job_id, source.term_id, ?);
            """

    GET_SEARCH_TERM_VALIDITIES_FROM_JOB = """
                SELECT st.term_text, jst.valid
                FROM job_search_terms jst
                JOIN search_terms st ON jst.term_id = st.term_id
                WHERE jst.job_id = ?
            """

    JOB_HTML_QUERY = "SELECT job_html FROM jobs WHERE job_number = ?"