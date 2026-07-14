"""
Custom exceptions for Mojaloop Production Service
"""

from fastapi import status


class CustomException(Exception):
    """Base custom exception class"""
    
    def __init__(self, message: str, name: str = "CustomException", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.name = name
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(CustomException):
    """Exception raised when a resource is not found"""
    
    def __init__(self, resource_name: str = "Resource", resource_id: str = None):
        message = f"{resource_name} not found"
        if resource_id:
            message += f" with ID: {resource_id}"
        super().__init__(
            message=message,
            name="NotFoundException",
            status_code=status.HTTP_404_NOT_FOUND
        )


class ConflictException(CustomException):
    """Exception raised when there's a conflict (e.g., duplicate resource)"""
    
    def __init__(self, resource_name: str = "Resource", detail: str = None):
        message = f"{resource_name} already exists"
        if detail:
            message += f": {detail}"
        super().__init__(
            message=message,
            name="ConflictException",
            status_code=status.HTTP_409_CONFLICT
        )


class ValidationException(CustomException):
    """Exception raised for validation errors"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            name="ValidationException",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class UnauthorizedException(CustomException):
    """Exception raised for unauthorized access"""
    
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(
            message=message,
            name="UnauthorizedException",
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenException(CustomException):
    """Exception raised for forbidden access"""
    
    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message,
            name="ForbiddenException",
            status_code=status.HTTP_403_FORBIDDEN
        )


class BadRequestException(CustomException):
    """Exception raised for bad requests"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            name="BadRequestException",
            status_code=status.HTTP_400_BAD_REQUEST
        )
