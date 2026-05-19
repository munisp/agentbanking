"""
Investment Service Exceptions
Custom exceptions for investment service
"""

class InvestmentServiceException(Exception):
    """Base exception for investment service"""
    pass

class InvestmentServiceNotFoundException(InvestmentServiceException):
    """Exception raised when investment service not found"""
    pass

class InvestmentServiceValidationException(InvestmentServiceException):
    """Exception raised when validation fails"""
    pass

class InvestmentServicePermissionException(InvestmentServiceException):
    """Exception raised when permission denied"""
    pass
