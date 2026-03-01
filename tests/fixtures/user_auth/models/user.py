"""User domain models."""


class BaseModel:
    """Base class for all domain models."""

    def __init__(self, id: int) -> None:
        """Initialize with a unique identifier."""
        self.id = id

    def to_dict(self) -> dict:
        """Serialize the model to a dictionary."""
        return {"id": self.id}

    @staticmethod
    def validate_id(id: int) -> bool:
        """Return True if the id is a positive integer."""
        return isinstance(id, int) and id > 0


class User(BaseModel):
    """Represents an authenticated user."""

    def __init__(self, id: int, username: str, email: str) -> None:
        """Initialize with id, username, and email."""
        super().__init__(id)
        self.username = username
        self.email = email

    def to_dict(self) -> dict:
        """Serialize the user to a dictionary including username and email."""
        base = super().to_dict()
        base.update({"username": self.username, "email": self.email})
        return base

    def display_name(self) -> str:
        """Return the display name for the user."""
        return self.username


def create_guest_user() -> "User":
    """Create and return a guest user instance with default values."""
    return User(id=1, username="guest", email="guest@example.com")
