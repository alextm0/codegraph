"""User domain models."""


class BaseModel:
    """Base class for all domain models."""

    def __init__(self, id: int) -> None:
        """
        Create a BaseModel with the given identifier.
        
        Parameters:
            id (int): Unique identifier for the model; must be greater than or equal to 1. Stored on the instance as `id`.
        """
        self.id = id

    def to_dict(self) -> dict:
        """
        Serialize the model into a dictionary containing its identifier.
        
        Returns:
            dict: A dictionary with the key "id" mapped to the model's identifier.
        """
        return {"id": self.id}

    @staticmethod
    def validate_id(id: int) -> bool:
        """
        Determine whether the given id is a positive integer.
        
        Parameters:
            id (int): The identifier to validate.
        
        Returns:
            bool: `True` if `id` is an integer greater than zero, `False` otherwise.
        """
        return isinstance(id, int) and id > 0


class User(BaseModel):
    """Represents an authenticated user."""

    def __init__(self, id: int, username: str, email: str) -> None:
        """
        Initialize a User with a unique identifier, username, and email address.
        
        Parameters:
            id (int): Unique identifier for the user.
            username (str): The user's username or display name.
            email (str): The user's email address.
        """
        super().__init__(id)
        self.username = username
        self.email = email

    def to_dict(self) -> dict:
        """
        Serialize the user into a dictionary containing its id, username, and email.
        
        Returns:
            dict: A dictionary with keys 'id', 'username', and 'email' mapping to the user's values.
        """
        base = super().to_dict()
        base.update({"username": self.username, "email": self.email})
        return base

    def display_name(self) -> str:
        """
        Get the user's display name.
        
        Returns:
            str: The display name, which is the user's username.
        """
        return self.username


def create_guest_user() -> "User":
    """
    Create a guest user with preset default attributes.
    
    Returns:
        User: A guest User with id=1, username="guest", and email="guest@example.com".
    """
    return User(id=1, username="guest", email="guest@example.com")
