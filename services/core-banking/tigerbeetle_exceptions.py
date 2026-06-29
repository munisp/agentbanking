"""
TigerBeetle Custom Exceptions
Comprehensive error handling for TigerBeetle operations
"""

from typing import Optional, Dict, Any


class TigerBeetleError(Exception):
    """Base exception for all TigerBeetle errors"""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'code': self.code,
            'details': self.details
        }


class AccountError(TigerBeetleError):
    """Base exception for account-related errors"""
    pass


class AccountNotFoundError(AccountError):
    """Raised when account is not found"""
    
    def __init__(self, account_id: int) -> None:
        super().__init__(
            message=f"Account {account_id} not found",
            code="ACCOUNT_NOT_FOUND",
            details={'account_id': account_id}
        )


class AccountAlreadyExistsError(AccountError):
    """Raised when account already exists"""
    
    def __init__(self, account_id: int) -> None:
        super().__init__(
            message=f"Account {account_id} already exists",
            code="ACCOUNT_ALREADY_EXISTS",
            details={'account_id': account_id}
        )


class InsufficientBalanceError(AccountError):
    """Raised when account has insufficient balance"""
    
    def __init__(self, account_id: int, required: int, available: int) -> None:
        super().__init__(
            message=f"Insufficient balance in account {account_id}. Required: {required}, Available: {available}",
            code="INSUFFICIENT_BALANCE",
            details={
                'account_id': account_id,
                'required': required,
                'available': available,
                'shortfall': required - available
            }
        )


class TransferError(TigerBeetleError):
    """Base exception for transfer-related errors"""
    pass


class TransferValidationError(TransferError):
    """Raised when transfer validation fails"""
    
    def __init__(self, errors: list) -> None:
        super().__init__(
            message=f"Transfer validation failed: {', '.join(errors)}",
            code="TRANSFER_VALIDATION_ERROR",
            details={'errors': errors}
        )


class TransferNotFoundError(TransferError):
    """Raised when transfer is not found"""
    
    def __init__(self, transfer_id: int) -> None:
        super().__init__(
            message=f"Transfer {transfer_id} not found",
            code="TRANSFER_NOT_FOUND",
            details={'transfer_id': transfer_id}
        )


class DuplicateTransferError(TransferError):
    """Raised when transfer ID already exists"""
    
    def __init__(self, transfer_id: int) -> None:
        super().__init__(
            message=f"Transfer {transfer_id} already exists",
            code="DUPLICATE_TRANSFER",
            details={'transfer_id': transfer_id}
        )


class ConnectionError(TigerBeetleError):
    """Raised when connection to TigerBeetle fails"""
    
    def __init__(self, replica_address: str, reason: Optional[str] = None) -> None:
        super().__init__(
            message=f"Failed to connect to TigerBeetle at {replica_address}",
            code="CONNECTION_ERROR",
            details={'replica_address': replica_address, 'reason': reason}
        )


class TimeoutError(TigerBeetleError):
    """Raised when operation times out"""
    
    def __init__(self, operation: str, timeout_seconds: int) -> None:
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds} seconds",
            code="TIMEOUT_ERROR",
            details={'operation': operation, 'timeout_seconds': timeout_seconds}
        )


class CurrencyError(TigerBeetleError):
    """Base exception for currency-related errors"""
    pass


class UnsupportedCurrencyError(CurrencyError):
    """Raised when currency is not supported"""
    
    def __init__(self, currency: str) -> None:
        supported = ['NGN', 'USD', 'EUR', 'GBP', 'CNY', 'GHS', 'KES', 'ZAR']
        super().__init__(
            message=f"Currency '{currency}' is not supported. Supported currencies: {', '.join(supported)}",
            code="UNSUPPORTED_CURRENCY",
            details={'currency': currency, 'supported_currencies': supported}
        )


class CurrencyMismatchError(CurrencyError):
    """Raised when currencies don't match"""
    
    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            message=f"Currency mismatch. Expected: {expected}, Actual: {actual}",
            code="CURRENCY_MISMATCH",
            details={'expected': expected, 'actual': actual}
        )


class BatchError(TigerBeetleError):
    """Base exception for batch operation errors"""
    pass


class BatchSizeExceededError(BatchError):
    """Raised when batch size exceeds limit"""
    
    def __init__(self, actual_size: int, max_size: int) -> None:
        super().__init__(
            message=f"Batch size {actual_size} exceeds maximum {max_size}",
            code="BATCH_SIZE_EXCEEDED",
            details={'actual_size': actual_size, 'max_size': max_size}
        )


class PartialBatchFailureError(BatchError):
    """Raised when some items in batch fail"""
    
    def __init__(self, total: int, successful: int, failed: int, errors: list) -> None:
        super().__init__(
            message=f"Batch partially failed. Total: {total}, Successful: {successful}, Failed: {failed}",
            code="PARTIAL_BATCH_FAILURE",
            details={
                'total': total,
                'successful': successful,
                'failed': failed,
                'errors': errors
            }
        )


class ConfigurationError(TigerBeetleError):
    """Raised when configuration is invalid"""
    
    def __init__(self, parameter: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid configuration for '{parameter}': {reason}",
            code="CONFIGURATION_ERROR",
            details={'parameter': parameter, 'reason': reason}
        )


class CircuitBreakerOpenError(TigerBeetleError):
    """Raised when circuit breaker is open"""
    
    def __init__(self, service: str, failure_count: int) -> None:
        super().__init__(
            message=f"Circuit breaker open for '{service}' after {failure_count} failures",
            code="CIRCUIT_BREAKER_OPEN",
            details={'service': service, 'failure_count': failure_count}
        )


# Error code mapping for TigerBeetle native errors
TIGERBEETLE_ERROR_CODES = {
    1: ("EXCEEDS_CREDITS", InsufficientBalanceError),
    2: ("EXCEEDS_DEBITS", AccountError),
    3: ("ACCOUNT_NOT_FOUND", AccountNotFoundError),
    4: ("ACCOUNT_ALREADY_EXISTS", AccountAlreadyExistsError),
    5: ("TRANSFER_NOT_FOUND", TransferNotFoundError),
    6: ("DUPLICATE_TRANSFER", DuplicateTransferError),
}


def map_tigerbeetle_error(error_code: int, context: Optional[Dict[str, Any]] = None) -> TigerBeetleError:
    """
    Map TigerBeetle error code to custom exception
    
    Args:
        error_code: TigerBeetle error code
        context: Additional context for the error
    
    Returns:
        TigerBeetleError: Mapped exception
    """
    if error_code in TIGERBEETLE_ERROR_CODES:
        code_name, exception_class = TIGERBEETLE_ERROR_CODES[error_code]
        
        # Try to instantiate with context
        try:
            if context:
                return exception_class(**context)
            else:
                return exception_class("Unknown")
        except TypeError:
            # Fallback to generic error
            return TigerBeetleError(
                message=f"TigerBeetle error: {code_name}",
                code=code_name,
                details=context or {}
            )
    
    return TigerBeetleError(
        message=f"Unknown TigerBeetle error code: {error_code}",
        code="UNKNOWN_ERROR",
        details={'error_code': error_code, 'context': context}
    )
