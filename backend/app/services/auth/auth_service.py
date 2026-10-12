from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import UnauthorizedException, RepoSageException


class AuthService:
    @staticmethod
    def register_user(db: Session, email: str, password: str) -> User:
        """Register a new user with hashed password."""
        email_clean = email.strip().lower()
        existing = db.query(User).filter(User.email == email_clean).first()
        if existing:
            raise RepoSageException("An account with this email already exists.", code="USER_ALREADY_EXISTS")
        
        user = User(
            email=email_clean,
            password_hash=hash_password(password),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Tuple[User, str, str]:
        """Authenticate user by email and password, returning user, access token, and refresh token."""
        email_clean = email.strip().lower()
        user = db.query(User).filter(User.email == email_clean).first()
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password.")
        
        if not user.is_active:
            raise UnauthorizedException("Account has been deactivated.")

        access_token = create_access_token({"sub": user.id, "email": user.email})
        refresh_token = create_refresh_token({"sub": user.id})
        return user, access_token, refresh_token

    @staticmethod
    def refresh_token(db: Session, refresh_token_str: str) -> Tuple[User, str, str]:
        """Validate refresh token and issue new token pair (refresh token rotation)."""
        try:
            payload = decode_token(refresh_token_str)
            if payload.get("type") != "refresh":
                raise UnauthorizedException("Provided token is not a refresh token.")
            user_id = payload.get("sub")
        except Exception as e:
            raise UnauthorizedException(f"Invalid refresh token: {str(e)}")

        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise UnauthorizedException("User associated with token no longer exists or is inactive.")

        new_access = create_access_token({"sub": user.id, "email": user.email})
        new_refresh = create_refresh_token({"sub": user.id})
        return user, new_access, new_refresh

    @staticmethod
    def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()
