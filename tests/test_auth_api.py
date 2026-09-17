import pytest
import tempfile
import os
import time
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from libs.auth.repository import UserRepository
from libs.auth.dependencies import get_user_repository
from libs.auth.security import hash_password, verify_password, create_access_token, decode_access_token

@pytest.fixture
def auth_client():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "auth_test_users.db")
    repo = UserRepository(db_path)

    # Explicitly override the user repository for auth endpoints
    app.dependency_overrides[get_user_repository] = lambda: repo
    client = TestClient(app)
    
    yield client, repo

    app.dependency_overrides.pop(get_user_repository, None)
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rmdir(temp_dir)
    except Exception:
        pass

def test_password_hashing_and_verification():
    raw_password = "supersecret_password_123"
    pwd_hash, salt = hash_password(raw_password)
    
    assert pwd_hash is not None and len(pwd_hash) == 64
    assert salt is not None and len(salt) == 32
    assert verify_password(raw_password, pwd_hash, salt) is True
    assert verify_password("wrong_password", pwd_hash, salt) is False

def test_jwt_token_generation_and_expiry():
    user_id = "test-user-123"
    username = "alice"
    
    # Valid token
    token = create_access_token(user_id, username, expires_delta=timedelta(minutes=15))
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["username"] == username
    
    # Expired token
    expired_token = create_access_token(user_id, username, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ValueError, match="Token has expired"):
        decode_access_token(expired_token)
        
    # Tampered token
    tampered_token = token[:-5] + "aaaaa"
    with pytest.raises(ValueError, match="JWT signature verification failed"):
        decode_access_token(tampered_token)

def test_register_success_and_duplicates(auth_client):
    client, _ = auth_client
    
    # Valid registration
    res = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "username": "alice",
        "password": "SecurePassword123"
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["username"] == "alice"
    assert "password_hash" not in data["user"]
    assert "salt" not in data["user"]

    # Duplicate username
    res_dup_user = client.post("/api/v1/auth/register", json={
        "email": "alice_other@example.com",
        "username": "alice",
        "password": "SecurePassword123"
    })
    assert res_dup_user.status_code == 400
    assert "already taken" in res_dup_user.json()["detail"]

    # Duplicate email
    res_dup_email = client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "username": "alice2",
        "password": "SecurePassword123"
    })
    assert res_dup_email.status_code == 400
    assert "already registered" in res_dup_email.json()["detail"]

def test_register_validation_failures(auth_client):
    client, _ = auth_client
    
    # Password too short (< 8 chars)
    res = client.post("/api/v1/auth/register", json={
        "email": "short@example.com",
        "username": "shortpass",
        "password": "123"
    })
    assert res.status_code == 422

    # Invalid email format
    res_bad_email = client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "username": "bademail",
        "password": "SecurePassword123"
    })
    assert res_bad_email.status_code == 422

def test_login_and_me_endpoint(auth_client):
    client, _ = auth_client
    
    # Register user
    client.post("/api/v1/auth/register", json={
        "email": "bob@example.com",
        "username": "bob",
        "password": "BobSecurePassword123"
    })
    
    # Successful login
    login_res = client.post("/api/v1/auth/login", json={
        "username": "bob",
        "password": "BobSecurePassword123"
    })
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]
    
    # Unauthenticated /me request
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401
    
    # Authenticated /me request
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "bob"
    assert me_data["email"] == "bob@example.com"

def test_idor_repository_and_session_isolation(auth_client):
    client, user_repo = auth_client
    
    # Register User 1 (Alice)
    client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "username": "alice",
        "password": "Password123!"
    })
    alice_token = client.post("/api/v1/auth/login", json={
        "username": "alice",
        "password": "Password123!"
    }).json()["access_token"]
    
    # Register User 2 (Bob)
    client.post("/api/v1/auth/register", json={
        "email": "bob@example.com",
        "username": "bob",
        "password": "Password123!"
    })
    bob_token = client.post("/api/v1/auth/login", json={
        "username": "bob",
        "password": "Password123!"
    }).json()["access_token"]
    
    alice_profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {alice_token}"}).json()
    bob_profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bob_token}"}).json()
    
    # Assign repo and session exclusively to Alice
    repo_id = "alice-private-repo"
    session_id = "alice-private-session"
    user_repo.assign_repository_owner(alice_profile["id"], repo_id)
    user_repo.assign_session_owner(alice_profile["id"], session_id)
    
    # Verify Alice has access
    assert user_repo.is_repository_owner(alice_profile["id"], repo_id) is True
    assert user_repo.is_session_owner(alice_profile["id"], session_id) is True
    
    # Verify Bob is denied access
    assert user_repo.is_repository_owner(bob_profile["id"], repo_id) is False
    assert user_repo.is_session_owner(bob_profile["id"], session_id) is False
    
    # Test HTTP endpoint IDOR defense: Bob attempting to delete Alice's repository
    bob_delete_res = client.delete(
        f"/api/v1/repositories/{repo_id}",
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert bob_delete_res.status_code == 403
    assert "Forbidden" in bob_delete_res.json()["detail"]

    # Test HTTP endpoint IDOR defense: Bob attempting to read Alice's chat session
    bob_chat_res = client.get(
        f"/api/v1/chat/sessions/{session_id}",
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert bob_chat_res.status_code == 403
    assert "Forbidden" in bob_chat_res.json()["detail"]
