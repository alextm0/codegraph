"""User domain models."""


class BaseModel:
    """Base class for all domain models."""

    def __init__(self, id: int) -> None:
        """
        Initialize the model with a unique identifier.
        
        Parameters:
            id (int): The model's unique identifier; must be an integer greater than 0.
        """
        self.id = id

    def to_dict(self) -> dict:
        """
        Return a dictionary representation containing the model's identifier.
        
        Returns:
            dict: A dictionary with the key "id" mapped to the model's identifier.
        """
        return {"id": self.id}

    @staticmethod
    def validate_id(id: int) -> bool:
        """
        Determine whether the given identifier is an integer greater than 0.
        
        Parameters:
            id (int): Identifier to validate.
        
        Returns:
            bool: `True` if id is an integer greater than 0, `False` otherwise.
        """
        return isinstance(id, int) and id > 0


class User(BaseModel):
    """Represents an authenticated user."""

    def __init__(self, id: int, username: str, email: str) -> None:
        """
        Create a User instance and set its identifier, username, and email.
        
        Parameters:
            id (int): Unique identifier for the user.
            username (str): Username for display and authentication.
            email (str): User's email address.
        """
        super().__init__(id)
        self.username = username
        self.email = email

    def to_dict(self) -> dict:
        """
        Serialize the user to a dictionary including its id, username, and email.
        
        Returns:
            dict: A dictionary with keys "id", "username", and "email".
        """
        base = super().to_dict()
        base.update({"username": self.username, "email": self.email})
        return base

    def display_name(self) -> str:
        """
        Get the user's display name.
        
        Returns:
            display_name (str): The user's username.
        """
        return self.username


def create_guest_user() -> "User":
    """
    Create a guest User with id 0, username "guest", and email "guest@example.com".
    
    Returns:
        A User instance representing a guest with id 0, username "guest", and email "guest@example.com".
    """
    return User(id=0, username="guest", email="guest@example.com")
