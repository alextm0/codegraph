"""Utility functions for input validation."""

import re
import logging

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """
    Determine whether an email address matches a basic email format.
    
    Parameters:
        email (str): The email address to validate.
    
    Returns:
        bool: `True` if the email matches the expected format, `False` otherwise.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> bool:
    """
    Determine whether a username is valid based on length and allowed characters.
    
    A valid username is between 3 and 32 characters long (inclusive) and contains only letters, digits, or underscores.
    
    Parameters:
        username (str): The username to validate.
    
    Returns:
        `true` if the username meets the requirements, `false` otherwise.
    """
    if len(username) < 3 or len(username) > 32:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_]+$", username))


def validate_password(password: str) -> bool:
    """
    Check whether a password meets the module's minimum security requirements.
    
    Returns:
        True if the password is at least eight characters long and contains at least one digit and one uppercase letter, False otherwise.
    """
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    return validate_password_strength(password) and has_digit and has_upper


def validate_password_strength(password: str) -> bool:
    """
    Check whether a password meets the minimum length requirement.
    
    Parameters:
        password (str): Password to validate.
    
    Returns:
        True if the password length is at least 8 characters, False otherwise.
    """
    return len(password) >= 8
