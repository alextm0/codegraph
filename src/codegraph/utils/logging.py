"""Logging configuration."""

import logging
import sys

def setup_logging(level=logging.INFO):
    """Configure basic logging.
    
    Sets the root logger to WARNING to suppress noise from external libraries,
    and sets the 'codegraph' logger to the specified level (default INFO).
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("codegraph").setLevel(level)
