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
        """Register a new user and return the created User instance."""
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
        """Return the User with the given username, or None if not found."""
        return self._users.get(username)
