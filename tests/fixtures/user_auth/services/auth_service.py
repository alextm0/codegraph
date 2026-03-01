"""Authentication service for user registration and login."""

from user_auth.models.user import User
from user_auth.utils.validators import validate_email, validate_username, validate_password


class AuthService:
    """Handles user registration and authentication."""

    def __init__(self) -> None:
        """Initialize with an empty user store."""
        self._users: dict[str, User] = {}
        self._next_id: int = 1

    def register(self, username: str, email: str, password: str) -> User:
        """
        Create and store a new user after validating username, email, and password.
        
        Returns:
            User: The newly created user with an assigned `id`, `username`, and `email`.
        
        Raises:
            ValueError: If a user with `username` already exists.
            ValueError: If `username` fails validation.
            ValueError: If `email` fails validation.
            ValueError: If `password` does not meet requirements.
        """
        if username in self._users:
            raise ValueError(f"User already exists: {username}")
        if not validate_username(username):
            raise ValueError(f"Invalid username: {username}")
        if not validate_email(email):
            raise ValueError(f"Invalid email: {email}")
        if not validate_password(password):
            raise ValueError("Password does not meet requirements")
        user = User(id=self._next_id, username=username, email=email)
        self._users[username] = user
        self._next_id += 1
        return user

    def get_user(self, username: str) -> User | None:
        """
        Retrieve a user by username.
        
        Returns:
            User | None: `User` if a user with the given username exists, `None` otherwise.
        """
        return self._users.get(username)
