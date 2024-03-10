import os
from urllib.parse import urlparse


def create_folder_if_not_exists(folder_path):
    """Create a folder if it doesn't already exist."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Folder created: {folder_path}")
    else:
        print(f"Folder already exists: {folder_path}")


def get_file_extension(url):
    """Extract the file extension from a URL."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    extension = path.split(".")[-1] if "." in path else ""
    return extension
