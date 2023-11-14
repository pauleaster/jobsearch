
# JobScraper

Usage:

```python
scraper = JobScraper()
scraper.perform_searches(["C++", "python", "data science"])
```

The resulting job URLs are stored in a PostgreSQL database, categorized based on whether the search term was found in the resulting job description or not.

Some job websites use AI techniques to perform searches, and some results are promoted for commercial reasons. Therefore, the search term is not always present in the resulting job description. This application performs an additional search to ensure that the search term is explicitly present in the job descriptions.

## URL Configuration

To set up the URL to be searched, enter the following data in the file `~/.scraper/scraper.conf`:

```ini
[DEFAULT]
URL = https://url.for.job.search/jobs
```

This URL is searched using the supplied search terms, which are entered into the form named `keywords-input`. The resulting search should yield links to available jobs. The expected format for the job URLs is:

```url
https://url.for.job.search/job/[job_number]
```

## Database Configuration

To store job data, this application now uses a PostgreSQL database. Before running the application, ensure that you've set up a PostgreSQL instance and added the appropriate configuration.

### Setting Up PostgreSQL

- Install and start the PostgreSQL service.
- Create a database and user for this application.

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

### Permissions

Ensure that the `scraper.conf` file is readable only by the user running the application to prevent potential security risks.

These results are specific to the job search website that was used as a basis; however, the code can be modified to suit your requirements.
