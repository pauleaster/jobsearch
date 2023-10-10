"""
config.py

Provides configuration loading functionality for the scraper tool.

This module attempts to load the configuration from `~/.scraper/scraper.conf`:
- Reads the JOB_SCRAPER_URL from the configuration.
- Raises an error if the configuration file or necessary keys are missing.

Example configuration:
[DEFAULT]
URL = https://url.for.job.search/jobs

Note:
Ensure that the configuration file exists and has the required keys before
running any scraper tool that depends on this module.
"""
import configparser
import os

config = configparser.ConfigParser(interpolation=None)
config_path = os.path.expanduser("~/.scraper/scraper.conf")

if os.path.exists(config_path):
    config.read(config_path)
    if "URL" in config["DEFAULT"]:
        JOB_SCRAPER_DEFAULT_URL = config["DEFAULT"]["URL"]
    else:
        raise ValueError("URL key not found in the configuration file!")
    if "URL" in config["REMOTE"]:
        JOB_SCRAPER_REMOTE_URL = config["REMOTE"]["URL"]
    else:
        raise ValueError("URL key not found in the REMOTE section of the configuration file!")

else:
    raise ValueError(f"Configuration file not found at {config_path}")
