
from scraper_module.scraper import JobScraper, LinkStatus


if __name__ == "__main__":
    # Usage:
    scraper = JobScraper()
    scraper.perform_searches(["pandas","numpy","matplotlib"])
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
