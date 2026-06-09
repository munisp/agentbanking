"""
Rewards Service Exceptions
Custom exceptions for rewards service
"""

class RewardsServiceException(Exception):
    """Base exception for rewards service"""
    pass

class RewardsServiceNotFoundException(RewardsServiceException):
    """Exception raised when rewards service not found"""
    pass

class RewardsServiceValidationException(RewardsServiceException):
    """Exception raised when validation fails"""
    pass

class RewardsServicePermissionException(RewardsServiceException):
    """Exception raised when permission denied"""
    pass
