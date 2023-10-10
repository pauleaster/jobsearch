
from scraper_module.scraper import JobScraper, LinkStatus


SEARCH_TERMS = [
    "C++",
    "python",
    "software engineer",
    "software developer",
    "rust",    
    "pandas",
    "numpy",
    "matplotlib",
    "C#",
    "backend",
    "data science",
    "artificial intelligence",
    "chatgpt",
    "programmer"
]

search_terms = [f'{s}' for s in SEARCH_TERMS]

if __name__ == "__main__":
    # Usage:
    scraper = JobScraper()
    scraper.perform_searches(search_terms)
    print(
        f"Validated links length: {scraper.job_data.get_link_count(LinkStatus.VALID)}"
    )
    print(
        f"Invalidated links length: {scraper.job_data.get_link_count(LinkStatus.INVALID)}"
    )
    print(
        f"Valid links read: {scraper.job_data.get_links_difference(LinkStatus.VALID)}"
    )
    print(
        f"Invalid links read: {scraper.job_data.get_links_difference(LinkStatus.INVALID)}"
    )
