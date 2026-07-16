import secrets
import string
import logging

from utils import UserRole

def generate_api_key(length=16) -> str:
    characters = string.ascii_letters + string.digits
    api_key = ''.join(secrets.choice(characters) for _ in range(length))
    return api_key

def create_logger(module: str):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(module)
