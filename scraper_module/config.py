import configparser
import os

config = configparser.ConfigParser()
config_path = os.path.expanduser("~/.scraper/scraper.conf")

if os.path.exists(config_path):
    config.read(config_path)
    if "URL" in config["DEFAULT"]:
        JOB_SCRAPER_URL = config["DEFAULT"]["URL"]
    else:
        raise ValueError("URL key not found in the configuration file!")
else:
    raise ValueError(f"Configuration file not found at {config_path}")
