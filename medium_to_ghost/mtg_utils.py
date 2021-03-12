import logging
import urllib.request
from pathlib import Path
from urllib.error import HTTPError


def download_with_local_cache(url: str, cache_folder: Path, filename_creator):
    """
    Download URL content to local file if it doesn't already exist.
    :param url: URL to download
    :param cache_folder: Where to cache the result
    :param filename_creator: Callback to process filename
    :return: The local path the result is saved to (either downloaded or previously cached)
    """
    # Ensure cache folder exists.
    cache_folder.mkdir(parents=True, exist_ok=True)

    # Send a User Agent so Medium doesn't return 403.
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'medium_to_ghost post exporter')]
    urllib.request.install_opener(opener)

    logging.info(f"Downloading {url} to {cache_folder}")

    # Create local filename from URI with filename_creator.
    uri = url.split("/")[-1]
    filename = filename_creator(uri)

    local_destination = cache_folder / filename

    if local_destination.exists():
        logging.info(f"{local_destination} already exists. Using cached copy.")
    else:
        try:
            local_filename, headers = urllib.request.urlretrieve(url, local_destination)
        except HTTPError as e:
            logging.error(f"Download failed for {local_destination}. Error Message: {e.msg}")

    return local_destination
