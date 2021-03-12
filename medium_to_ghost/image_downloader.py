import logging
from pathlib import Path
import imghdr

from medium_to_ghost.mtg_utils import download_with_local_cache


def get_file_with_extension(local_destination: Path):
    """
    Tests a downloaded image for its file extension & returns a corrected one.
    :param local_destination: The local path of the image
    """
    if len(local_destination.suffixes) == 0:
        local_destination_to_fix = Path(local_destination)
        image_extension = imghdr.what(local_destination_to_fix)
        return local_destination_to_fix.with_suffix("." + image_extension)
    else:
        return local_destination


def image_filename_creator(url):
    filename = url.split("/")[-1]
    # Medium has stars (*) in image filenames but ghost doesn't like this
    return filename.replace("*", "-")


def download_image_with_local_cache(url: str, cache_folder: Path):
    """
    Download an image file locally if it doesn't already exist.
    :param url: Image url to download
    :param cache_folder: Where to cache the image
    :return: The local path of the image (either downloaded or previously cached)
    """
    local_destination = download_with_local_cache(url, cache_folder, image_filename_creator)

    fixed_filename_at_local_destination = get_file_with_extension(local_destination)
    if len(local_destination.suffixes) == 0:
        logging.info(f"Fixed extension of {local_destination.name} to {fixed_filename_at_local_destination.name}.")
        local_destination.rename(fixed_filename_at_local_destination)
        return fixed_filename_at_local_destination
    else:
        return local_destination
