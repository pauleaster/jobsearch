"""
delays.py
---------

This module defines the delay constants for network handling and
determines the number of retries for requests.
"""

from enum import Enum


class DelaySettings(Enum):
    """
    Delay constants for network handling
    """

    SELENIUM_INTERACTION_DELAY = 1
    SCROLL_TO_NEXT_BUTTON_DELAY = 6
    SUCCESSIVE_URL_READ_DELAY = 6
    CLOUDFLARE_RETRY_DELAY = 300
    REQUEST_EXCEPTION_DELAY = 5
    REQUEST_TIMEOUT = 10
    NUM_RETRIES = 4
    EXPIRED_RESET_TIME_HOURS = 48
    VARIANCE_FACTOR = 0.2  # 20% variance for delays
