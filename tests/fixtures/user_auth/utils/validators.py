"""Utility functions for input validation."""

import re
import logging

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """
    Determine whether an email address is in a valid format.
    
    Returns:
        bool: True if the email matches the expected pattern, False otherwise. This validates only the syntactic format, not deliverability or domain existence.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """
    Ensure the username length is between 3 and 32 characters and contains only letters, digits, or underscores.
    
    Returns:
        `True` if the username meets the length and character requirements, `False` otherwise.
    """
    if len(username) < 3 or len(username) > 32:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_]+$", username))


def validate_password(password: str) -> bool:
    """
    Determine whether a password meets minimum security requirements.
    
    A valid password is at least 8 characters long, contains at least one digit, and contains at least one uppercase letter.
    
    Returns:
        `true` if the password meets these requirements, `false` otherwise.
    """
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return validate_password_strength(password) and has_digit and has_upper


def validate_password_strength(password: str) -> bool:
    """
    Check whether a password meets the minimum length requirement.
    
    Returns:
        `true` if the password length is at least 8 characters, `false` otherwise.
    """
    return len(password) >= 8
