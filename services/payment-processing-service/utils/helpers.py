import qrcode
import logging
import base64
from io import BytesIO

def create_logger(module: str):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.INFO)

    return logging.getLogger(module)

def generate_qr_base64(data: str) -> str:
        qr = qrcode.make(data)

        buffer = BytesIO()
        
        qr.save(buffer, "PNG")

        qr_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        return qr_base64
