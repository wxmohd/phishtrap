# app/logger.py
import logging, os

os.makedirs("./logs", exist_ok=True)
LOG_PATH = "./logs/phishtrap.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)

log = logging.getLogger("phishtrap")
