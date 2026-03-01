"""Authentication service for user registration and login."""

from user_auth.models.user import User
from user_auth.utils.validators import validate_email, validate_username, validate_password


class AuthService:
    """Handles user registration and authentication."""

    def __init__(self) -> None:
        """
        Create an AuthService with an empty in-memory user store and the next user ID initialized to 1.
        
        Initializes internal state:
        - _users: dictionary mapping username (str) to User.
        - _next_id: integer used to assign unique user IDs starting at 1.
        """
        self._users: dict[str, User] = {}
        self._next_id: int = 1

    def register(self, username: str, email: str, password: str) -> User:
        """
        Create a new user after validating username, email, and password.
        
        Returns:
            User: The newly created User with an assigned ID.
        
        Raises:
            ValueError: If the username is invalid, the email is invalid, or the password does not meet requirements.
        """
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
        Retrieve the user with the given username.
        
        Returns:
            The matching User if found, `None` otherwise.
        """
        return self._users.get(username)
