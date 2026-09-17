from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from .models import User
from .security import decode_access_token
from .repository import get_user_repository, UserRepository

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    FastAPI dependency that extracts and validates the Bearer JWT token.
    Raises HTTP 401 if token is missing, expired, or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identifier.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = user_repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user

def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Optional[User]:
    """
    Optional user authentication for public or transition endpoints.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            return user_repo.get_user_by_id(user_id)
    except Exception:
        return None
    return None

def require_repository_owner(
    repo_id: str,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    Verifies that the authenticated user owns or has access to the requested repository.
    Prevents IDOR (Insecure Direct Object Reference).
    """
    if not user_repo.is_repository_owner(current_user.id, repo_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have permission to access repository '{repo_id}'."
        )
    return current_user

def require_session_owner(
    session_id: str,
    current_user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repository)
) -> User:
    """
    Verifies that the authenticated user owns or has access to the requested chat session.
    Prevents IDOR across user chat conversations.
    """
    if not user_repo.is_session_owner(current_user.id, session_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: You do not have permission to access session '{session_id}'."
        )
    return current_user
