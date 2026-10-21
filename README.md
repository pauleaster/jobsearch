# JobScraper

Usage:

```python
scraper = JobScraper()
scraper.perform_searches(["C++", "python", "data science"])
```

## Updates

- Supports scraping from both remote and default URLs, with combined search (remote first) if enabled in config.
- Main job fields (salary, position, advertiser, location, work type, expired) are now extracted and stored.
- After an interruption, the scraper resumes from the saved search term, URL, and page, using the snapshot ID stored in `scraper_state.csv`. Normal completion clears the saved state.

## Running

Activate your environment and configure `~/.scraper/scraper.conf` as described below, then run from the repository root:

```sh
python main.py
```

The search terms assembled in `main.py` are used to query the configured job site. Search results are not necessarily true matches: a site's search may return a job that does not contain the requested term. For job/search-term pairs that are not already known, the scraper fetches the job page and validates the requested term against its visible text (not only a dedicated job-description field). Results are classified as valid when the term is found and invalid when it is not; both classifications are stored in the SQL Server database.

The progress counters distinguish links encountered from pages fetched. “Jobs processed” counts encountered job links, including links whose job/search-term pair is already known and can skip another network fetch. “Jobs scraped” counts successful page fetches that are then checked and classified; failed fetches and known pairs skipped without fetching do not increment it.

### Automatic snapshots

The normal scrape automatically creates a timestamped snapshot under `job_metadata/<UTC timestamp>/`, or resumes the snapshot recorded in `scraper_state.csv` after an interruption. The directory contains job-number-named `.html` files and `combined_job_search_results.csv`. Snapshot output is limited to valid jobs whose search term is in the scraper's configured HTML snapshot-term allowlist; it is not a snapshot of every encountered result. No separate metadata-generation command is required for the normal scrape.

## URL Configuration

Set up the required configuration in `~/.scraper/scraper.conf`. The job-site URLs are:

All configuration examples below are sections of the same `~/.scraper/scraper.conf` file.

```ini
[DEFAULT]
URL = https://url.for.job.search/jobs

[REMOTE]
URL = https://remote.url.for.job.search/jobs
```

The scraper uses the configured URL or URLs to search with its search terms, entered into the form named `keywords-input`. The resulting search should yield links to available jobs. The expected format for job URLs is:

```url
https://url.for.job.search/job/[job_number]
```

The following settings are optional. `USE_REMOTE` selects the remote URL when combined search is disabled; `COMBINED_SEARCH` searches both URLs, remote first. Both default to `false`.

```ini
[SCRAPER]
USE_REMOTE = false
COMBINED_SEARCH = false
```

## Database Configuration

The application stores job data in SQL Server. Before running it, set up the SQL Server instance and add the database settings to the same configuration file.

### Configuration

Add the database connection details to the existing configuration file `~/.scraper/scraper.conf`. Under a new `[DATABASE]` section, provide the details according to the authentication method you are using.

For SQL Server Authentication, include the following:

```ini
[DATABASE]
DB_NAME = your_db_name
DB_USER = your_db_user
DB_PASSWORD = your_db_password
AUTH_METHOD = SQL_SERVER_AUTH
DB_HOST = localhost
DB_PORT = 1433
```

For Windows Authentication, use:
```ini
[DATABASE]
DB_NAME = your_db_name
AUTH_METHOD = WINDOWS_AUTH
DB_HOST = localhost
DB_PORT = 1433
```

Replace `your_db_name`, `your_db_user`, and `your_db_password` with your actual database name, user, and password (for SQL Server Authentication). For Windows Authentication, `DB_USER` and `DB_PASSWORD` are not required as it uses the credentials of the logged-in Windows user.

## Logging Configuration

Logging configuration is required in the same `~/.scraper/scraper.conf` file:

```ini
[LOGGING]
LOG_DIR = C:\path\to\log\directory
```

### Permissions

Ensure that the `scraper.conf` file is readable only by the user running the application to prevent potential security risks.

## Optional and legacy tools

The normal scrape creates its snapshots automatically; `scripts/create_job_metadata.py` is legacy/backfill tooling for a separate CSV-fed workflow and is not required. `create_spreadsheet.py` is an optional tool for exporting database data to XLSX.

[`copilot/Copilot_HTML_Scraper_Timestamped_Runs.md`](copilot/Copilot_HTML_Scraper_Timestamped_Runs.md) documents the earlier CSV-fed workflow and is historical, not the current scrape instructions.

The scraper targets a particular job-site structure, but its configurable URLs and settings allow the implementation to be adapted to other sites.
