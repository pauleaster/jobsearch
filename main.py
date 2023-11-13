
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
    scraper = JobScraper(load_network_handler=True)
    scraper.perform_searches(search_terms)
    print(
        "Finished scraping.\n")
