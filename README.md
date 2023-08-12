# JobScraper

Usage:

```python
scraper = JobScraper()
scraper.perform_searches(["C++", "python"])
```

The resulting job URLs are output to ``valid_links.csv`` or ``invalid_links.csv`` depending on whether the search term was found in the resulting job description or not.
Some job websites use AI techniques to perform searches, and some results are promoted for commercial reasons. Therefore, the search term is not always present in the resulting job description.
An additional search is performed to ensure that the search term is present in the job descriptions of the jobs listed in ``valid_links.csv``.

To set up the URL to be searched, enter the following data in the file ``//home/.scraper/scraper.conf``:

```ini
[DEFAULT]
URL = https://url.for.job.search/jobs
```

This URL is searched using the supplied search terms, which are entered into the form named ``keywords-input``.
The resulting search should yield links to available jobs.
The expected format for the job URLs is:

```url
https://url.for.job.search/job/[job_number]
```

These links are then parsed, and if the search term is present in the job description page, the job link is added to the ``valid_links.csv`` file in the following format:

```csv
[search term],[job url],[job number]
```

For example:

```csv
C++,https://url.for.job.search/job/123456,123456
C++,https://url.for.job.search/job/654321,654321
python,https://url.for.job.search/job/55555,55555
```

If the search term is not present, then the job link is added to the ``invalid_links.csv`` file in the same format, noting that these results do not contain the search term.

These results are specific to the job search website that I used as a basis; however, the code can be modified to suit your requirements.
