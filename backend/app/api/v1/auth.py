from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse, RefreshTokenRequest, UserResponse
from app.schemas.common import APIResponse
from app.services.auth.auth_service import AuthService
from app.api.v1.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=APIResponse[UserResponse], status_code=status.HTTP_201_CREATED)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = AuthService.register_user(db, req.email, req.password)
    return APIResponse(
        success=True,
        message="User registered successfully",
        data=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password, returning JWT access and refresh tokens."""
    user, access_token, refresh_token = AuthService.authenticate_user(db, req.email, req.password)
    return APIResponse(
        success=True,
        message="Login successful",
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600
        )
    )


@router.post("/refresh", response_model=APIResponse[TokenResponse])
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Rotate and refresh an existing access token."""
    user, new_access, new_refresh = AuthService.refresh_token(db, req.refresh_token)
    return APIResponse(
        success=True,
        message="Token refreshed successfully",
        data=TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=3600
        )
    )


@router.post("/logout", response_model=APIResponse[dict])
def logout(current_user: User = Depends(get_current_user)):
    """Revoke user session."""
    return APIResponse(success=True, message="Logged out successfully", data={})


@router.get("/me", response_model=APIResponse[UserResponse])
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get the authenticated user's profile."""
    return APIResponse(
        success=True,
        message="User profile retrieved",
        data=UserResponse.model_validate(current_user)
    )
