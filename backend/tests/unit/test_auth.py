import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.services.auth.auth_service import AuthService
from app.core.exceptions import RepoSageException, UnauthorizedException


def test_password_hashing():
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_generation_and_decoding():
    payload = {"sub": "user-uuid-1234", "email": "dev@reposage.dev"}
    token = create_access_token(payload)
    decoded = decode_token(token)
    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["email"] == "dev@reposage.dev"
    assert decoded["type"] == "access"


def test_auth_service_registration_and_login(db_session):
    user = AuthService.register_user(db_session, "newdev@example.com", "SecurePassword999!")
    assert user.id is not None
    assert user.email == "newdev@example.com"

    # Duplicate registration fails
    with pytest.raises(RepoSageException) as exc:
        AuthService.register_user(db_session, "newdev@example.com", "AnotherPassword!")
    assert exc.value.code == "USER_ALREADY_EXISTS"

    # Authenticate success
    logged_in, access_token, refresh_token = AuthService.authenticate_user(
        db_session, "newdev@example.com", "SecurePassword999!"
    )
    assert logged_in.id == user.id
    assert access_token is not None

    # Authenticate invalid password
    with pytest.raises(UnauthorizedException):
        AuthService.authenticate_user(db_session, "newdev@example.com", "WrongPassword!")
