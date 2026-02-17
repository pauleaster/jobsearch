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
    SUCCESSIVE_URL_READ_DELAY = 3
    REQUEST_EXCEPTION_DELAY = 5
    REQUEST_TIMEOUT = 10
    NUM_RETRIES = 4
