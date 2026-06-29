import secrets
import string
import logging
from passlib.context import CryptContext

def encrypt_pin(pin: str):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(pin)

def verify_pin(pin: str, hash: str):
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(pin, hash)

def create_logger(module: str):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(module)

def generate_account_number(length: int = 10) -> str:
    """Generate a random account number of specified length."""
    
    digits = string.digits
    return ''.join(secrets.choice(digits) for _ in range(length))
