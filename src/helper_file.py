import os
import time
import shutil
import logging

from urllib.parse import urlparse

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def create_folder_if_not_exists(folder_path: str) -> None:
    """Create a folder if it doesn't already exist."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder created: {folder_path}")
    else:
        print(f"Folder already exists: {folder_path}")


def get_file_extension(url: str) -> str:
    """Extract the file extension from a URL."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    extension = path.split(".")[-1] if "." in path else ""
    return extension


def delete_old_subfolders(path):
    current_time = time.time()
    hour_ago = current_time - 3600  # 3600 seconds = 1 hour

    for folder_name in os.listdir(path):
        folder_path = os.path.join(path, folder_name)

        # Check if the path is a directory
        if os.path.isdir(folder_path):
            # Get the latest modified time of files within the folder
            latest_modified_time = max(
                [
                    os.path.getmtime(os.path.join(folder_path, file_name))
                    for file_name in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, file_name))
                ],
                default=0,
            )

            # Delete the subfolder if no new files were created within the last hour
            if latest_modified_time <= hour_ago:
                try:
                    # Remove the subfolder and its contents recursively
                    # os.rmdir(folder_path)
                    shutil.rmtree(folder_path, ignore_errors=True)
                    logger.info(f"Deleted folder: {folder_path}")
                except OSError as e:
                    logger.error(
                        f"Error deleting folder: {folder_path}. Reason: {str(e)}"
                    )
