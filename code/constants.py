import logging
import os
import sys

DATA_PATH="./data"
FILES_PATH="./data/files"
AGENTS_FILE = "./data/agents.txt"

if not os.path.exists(DATA_PATH):
    logging.error(f"Data directory {DATA_PATH} not found. Likely due to not running in main directory. Exiting")
    sys.exit(1)

if not os.path.exists(FILES_PATH):
    try:
        os.makedirs(FILES_PATH)
        logging.info(f"Successfully created files directory '{FILES_PATH}'")
    except OSError as e:
        logging.error(f"Error creating files directory '{FILES_PATH}': {e}")

logging.info("Successfully loaded constants")
