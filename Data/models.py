import random
from typing import List, Optional
from datetime import datetime, timedelta, date
import os
import re
from dataclasses import dataclass, asdict


current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)


class UserProfile:
    def __init__(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None
    ):
        # Validate that at least one field is provided
        if all(field is None for field in [username, email, password]):
            raise ValueError("At least one field (username, email, or password) must be provided")

        # Validate username if provided
        if username is not None:
            if not isinstance(username, str):
                raise ValueError("Username must be a string")
            if len(username) < 3:
                raise ValueError("Username must be at least 3 characters long")
            if not username.isalnum():
                raise ValueError("Username must contain only alphanumeric characters")

        # Validate email if provided
        if email is not None:
            if not isinstance(email, str):
                raise ValueError("Email must be a string")
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                raise ValueError("Invalid email format")

        # Validate password if provided
        if password is not None:
            if not isinstance(password, str):
                raise ValueError("Password must be a string")
            # Minimum 8 characters, at least one uppercase, one lowercase, one digit, one special character
            password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#^()[\]{}<>.,;:|~`_+=-]).{8,}$'
            if not re.match(password_pattern, password):
                raise ValueError("Password must be at least 8 characters and include uppercase, lowercase, number, and symbol")

        self.username = username
        self.email = email
        self.password = password
        self.validated = False

    def to_dict(self) -> dict:
        """Convert the profile to a dictionary, excluding None values"""
        return {
            k: v for k, v in {
                'username': self.username,
                'email': self.email,
                'password': self.password,
                'validated': self.validated,
            }.items() if v is not None
        }

    def __str__(self) -> str:
        return f"UserProfile(username={self.username}, email={self.email}, validated={self.validated})"


@dataclass
class Fido2Credential:
    credential_id: str  # base64url-encoded
    public_key: str     # base64url-encoded
    sign_count: int
    transports: Optional[List[str]] = None
    user_handle: Optional[str] = None
    rp_id: Optional[str] = None
    # Add any other fields as needed

    def to_dict(self) -> dict:
        return asdict(self)
