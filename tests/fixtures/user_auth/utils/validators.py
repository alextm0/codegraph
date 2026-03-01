"""Utility functions for input validation."""

import re
import logging

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Check if the email address has a valid format."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """Check if the username meets length and character requirements."""
    if len(username) < 3 or len(username) > 32:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_]+$", username))


def validate_password(password: str) -> bool:
    """Check if the password meets minimum security requirements."""
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return validate_password_strength(password) and has_digit and has_upper


def validate_password_strength(password: str) -> bool:
    """Return True if password length is acceptable."""
    return len(password) >= 8
