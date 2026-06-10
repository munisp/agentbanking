"""
Recurring Payments Exceptions
Custom exceptions for recurring payments
"""

class RecurringPaymentsException(Exception):
    """Base exception for recurring payments"""
    pass

class RecurringPaymentsNotFoundException(RecurringPaymentsException):
    """Exception raised when recurring payments not found"""
    pass

class RecurringPaymentsValidationException(RecurringPaymentsException):
    """Exception raised when validation fails"""
    pass

class RecurringPaymentsPermissionException(RecurringPaymentsException):
    """Exception raised when permission denied"""
    pass
