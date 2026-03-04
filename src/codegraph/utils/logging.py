"""Logging configuration."""

import logging
import sys

def setup_logging(level=logging.INFO):
    """Configure basic logging to stderr."""
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
