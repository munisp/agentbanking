"""
Refund Service Exceptions
Custom exceptions for refund service
"""

class RefundServiceException(Exception):
    """Base exception for refund service"""
    pass

class RefundServiceNotFoundException(RefundServiceException):
    """Exception raised when refund service not found"""
    pass

class RefundServiceValidationException(RefundServiceException):
    """Exception raised when validation fails"""
    pass

class RefundServicePermissionException(RefundServiceException):
    """Exception raised when permission denied"""
    pass
