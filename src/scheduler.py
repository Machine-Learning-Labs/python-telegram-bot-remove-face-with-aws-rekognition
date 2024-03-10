import os
import time
import logging

from timeloop import Timeloop
from datetime import timedelta

from dotenv import load_dotenv
from helper_file import delete_old_subfolders


# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
temporary_folder = os.getenv("TMP_FOLDER")

tl = Timeloop()

@tl.job(interval=timedelta(seconds=900))
def sample_job_every_2s():
    logger.info(f"CLEANING photos... current time : {time.ctime()}")
    delete_old_subfolders(temporary_folder)
    
if __name__ == "__main__":
    tl.start(block=True)
    
