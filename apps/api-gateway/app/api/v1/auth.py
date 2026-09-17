from fastapi import APIRouter, HTTPException, Depends, status
from libs.auth.models import UserCreate, UserLogin, TokenResponse, UserResponse, User
from libs.auth.security import verify_password, create_access_token
from libs.auth.repository import get_user_repository, UserRepository
from libs.auth.dependencies import get_current_user
from libs.logging import get_logger

logger = get_logger("auth_api")
router = APIRouter()

@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, user_repo: UserRepository = Depends(get_user_repository)):
    """
    Registers a new user account with hashed password and generates a JWT access token.
    """
    # Check if username or email already exists
    if user_repo.get_user_record_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_data.username}' is already taken."
        )

    if user_repo.get_user_record_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_data.email}' is already registered."
        )

    user = user_repo.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )
    logger.info("User registered successfully", user_id=user.id, username=user.username)

    token = create_access_token(user_id=user.id, username=user.username)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at
        )
    )

@router.post("/auth/login", response_model=TokenResponse)
def login(login_data: UserLogin, user_repo: UserRepository = Depends(get_user_repository)):
    """
    Authenticates user credentials and returns a signed JWT access token.
    """
    user_record = user_repo.get_user_record_by_username(login_data.username)
    if not user_record:
        # Also check by email
        user_record = user_repo.get_user_record_by_email(login_data.username)

    if not user_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user_record["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verify_password(login_data.password, user_record["password_hash"], user_record["salt"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(user_id=user_record["id"], username=user_record["username"])
    logger.info("User logged in successfully", user_id=user_record["id"], username=user_record["username"])

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user_record["id"],
            username=user_record["username"],
            email=user_record["email"],
            created_at=user_record["created_at"]
        )
    )

@router.get("/auth/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user profile.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        created_at=current_user.created_at
    )
