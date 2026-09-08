from fastapi import HTTPException, status


class RepoSageException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundException(RepoSageException):
    def __init__(self, entity: str, identifier: str):
        super().__init__(f"{entity} with ID '{identifier}' not found.", code="NOT_FOUND")


class UnauthorizedException(RepoSageException):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, code="UNAUTHORIZED")


class ForbiddenException(RepoSageException):
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(message, code="FORBIDDEN")


class SecurityValidationException(RepoSageException):
    def __init__(self, message: str):
        super().__init__(message, code="SECURITY_VIOLATION")


class LLMProviderException(RepoSageException):
    def __init__(self, message: str):
        super().__init__(message, code="LLM_PROVIDER_ERROR")
