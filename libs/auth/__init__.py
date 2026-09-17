# Authentication package for GITTY-AI
from .models import User, UserCreate, UserLogin, TokenResponse, UserResponse
from .security import hash_password, verify_password, create_access_token, decode_access_token
from .repository import UserRepository, get_user_repository
from .dependencies import get_current_user, get_current_user_optional, require_repository_owner, require_session_owner

__all__ = [
    "User",
    "UserCreate",
    "UserLogin",
    "TokenResponse",
    "UserResponse",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "UserRepository",
    "get_user_repository",
    "get_current_user",
    "get_current_user_optional",
    "require_repository_owner",
    "require_session_owner",
]
