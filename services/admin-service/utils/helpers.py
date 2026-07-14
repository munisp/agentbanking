import logging

def create_logger(module: str):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(module)
