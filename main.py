
from scraper_module.scraper import JobScraper, LinkStatus


SEARCH_TERMS = [
    "python",
    "pandas",
    "numpy",
    "scipy",
    "matplotlib",
    "scikit-learn",
    "tensorflow",
    "keras",
    "pytorch",
    "data science",
    "artificial intelligence",
    "chatgpt",    
    "react",
    "javascript",
    "sql server",
    "postgres",
    "C++",
    "software engineer",
    "software developer",
    "rust",    
    "C#",
    "backend",
    "programmer"
]

search_terms = [f'{s}' for s in SEARCH_TERMS]

if __name__ == "__main__":
    # Usage:
    scraper = JobScraper(load_network_handler=True)
    scraper.perform_searches(search_terms)
    print("Finished scraping.\n")
