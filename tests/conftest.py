import pytest
from datetime import datetime, timezone
import tempfile
import os

from libs.auth.models import User
from libs.auth.repository import UserRepository
from libs.auth.dependencies import get_current_user, get_user_repository
from app.main import app

@pytest.fixture
def mock_user():
    return User(
        id="test-user-id",
        email="test@example.com",
        username="testuser",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat()
    )

@pytest.fixture
def test_user_repo():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_users.db")
    repo = UserRepository(db_path)
    repo.create_user(username="testuser", email="test@example.com", password="hashed_pwd", user_id="test-user-id")
    # Grant permissions for commonly tested repository and session fixtures
    repo.assign_repository_owner("test-user-id", "test-repo")
    repo.assign_repository_owner("test-user-id", "repo-1")
    repo.assign_repository_owner("test-user-id", "error-repo")
    repo.assign_session_owner("test-user-id", "mock-session-id")
    repo.assign_session_owner("test-user-id", "error-session-id")
    yield repo
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def setup_auth_dependencies(request, mock_user, test_user_repo):
    # Do not auto-override in test_auth_api so real authentication and IDOR defenses can be evaluated
    if "test_auth_api" in request.node.nodeid:
        yield
        return

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_user_repository] = lambda: test_user_repo
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_user_repository, None)
