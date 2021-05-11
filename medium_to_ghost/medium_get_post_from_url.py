import json
import logging
from pathlib import Path

from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from dateparser import parse

from medium_to_ghost.image_downloader import download_image_with_local_cache
from medium_to_ghost.medium_additional_parser import post_filename_creator
from medium_to_ghost.medium_post_parser import MediumHTMLParser
from medium_to_ghost.medium_to_ghost import update_or_create_export_file, create_ghost_import_zip
from medium_to_ghost.mtg_utils import download_with_local_cache


def feed_filename_creator(uri):
    slug_parts = uri.split("/")
    author = slug_parts[-1]
    _, author_name = author.split('@')
    slug = "feed_" + author_name + ".xml"
    return slug


def get_feed_for_author(author_username, cache_folder):
    medium_feed_url_for_author = "https://medium.com/feed/" + author_username

    logging.info(f"Downloading {medium_feed_url_for_author}...")

    local_feed_file = download_with_local_cache(medium_feed_url_for_author, cache_folder, feed_filename_creator)

    if local_feed_file is not None:
        return local_feed_file
    else:
        return None


def get_posts_from_medium():
    requested_url = "https://medium.com/solana-labs/turbine-solanas-block-propagation-protocol-solves-the-scalability-trilemma-2ddba46a51db"
    post_author_web = "604b747c3c21e5003b373350"
    # post_author_local = "604b720ccd88dd0001aac471"
    post_author_local = "5951f5fca366002ebd5dbef7"
    post_author = post_author_local
    author_username = "@anatolyyakovenko"

    export_folder = Path("exported_content_from_url")
    export_folder.mkdir(parents=True, exist_ok=True)

    feed_cache_folder = export_folder / "downloaded_feeds"
    author_feed_file = get_feed_for_author(author_username, feed_cache_folder)

    if author_feed_file is not None:
        logging.info(f"Trying to parse feed...")
        convert_feed_file(author_feed_file, post_author, export_folder)
        return ""
    else:
        canonical_url = requested_url
        logging.info(f"Downloading {canonical_url} and trying to parse...")

        cache_folder = export_folder / "downloaded_posts"
        local_post_file = download_with_local_cache(canonical_url, cache_folder, post_filename_creator)

        convert_downloaded_post_to_ghost_json(local_post_file, canonical_url, post_author, export_folder)


def convert_feed_file(feed_file, user, export_folder):
    logging.info(f"Parsing downloaded feed: {feed_file.name}...")

    converted_posts = []

    with open(feed_file) as feed_content_wrapper:
        feed_content = feed_content_wrapper.read() \
            .replace('<atom:', '<') \
            .replace('</atom:', '</') \
            .replace('<dc:', '<') \
            .replace('</dc:', '</') \
            .replace(':encoded>', '>')
        root = ET.fromstring(feed_content)
        items = root[0].findall('item')

        for post_index, item in enumerate(items):
            converted_post = convert_feed_item_to_ghost_json(item, user, post_index)
            if converted_post is not None:
                converted_posts.append(converted_post)

    export_file = "medium_export_for_ghost.json"
    export_output = export_folder / export_file

    output = open(export_output, "w")

    # Finally create or append export file.
    export_data = update_or_create_export_file([], [], converted_posts, [], [])

    json_string = json.dumps(export_data, indent=2)

    json.dump(export_data, output, indent=2)

    output.flush()

    # TODO: test what happens at importing...
    # Put everything in a zip file for Ghost
    create_ghost_import_zip("exported_content_from_url")


def convert_feed_item_to_ghost_json(item, user, post_index):
    # Get title.
    title = item.find('title').text
    # Get and extract guid to uuid.
    uuid = item.find('guid').text.split('/')[-1]
    # Get and extract canonical medium url.
    canonical_url = item.find('link').text.split('?')[0:-1][0]
    # Now extract slug out of it.
    slug_parts = canonical_url.split('/')[-1]
    slug = slug_parts.replace("-" + uuid, '')

    # Get & convert dates.
    created_date = parse(item.find('pubDate').text)
    updated_date = parse(item.find('updated').text)
    created_at = published_at = int(created_date.timestamp() * 1000)
    updated_at = int(updated_date.timestamp() * 1000)

    # Get encoded content.
    encoded_content = item.find('content').text

    # All the remaining document-evel attributes we need to collect
    comment_id = None
    plain_text = None
    feature_image = None
    status = "published"

    # TODO: get subtitle from h4 in content
    # custom_excerpt = subtitle

    # Convert story body itself to mobiledoc format (As required by Ghost)
    parser = MediumHTMLParser()
    parser.feed(encoded_content)
    mobiledoc_post = parser.convert()

    # Download all the story's images to local disk cache folder
    for card_index, card in enumerate(mobiledoc_post["cards"]):
        card_type = card[0]
        if card_type == "image":
            data = card[1]
            url = data["src"]

            # Prevent the medium statistic pixel from getting transferred.
            if url.find('stat?') == -1:
                cache_folder = Path("exported_content_from_url") / "downloaded_images" / slug
                new_image_path = download_image_with_local_cache(url, cache_folder)

                # TODO: Fix this when Ghost fixes https://github.com/TryGhost/Ghost/issues/9821
                # Ghost 2.0.3 has a bug where it doesn't update imported image paths, so manually add
                # /content/images.
                final_image_path_for_ghost = str(new_image_path).replace("exported_content_from_url", "/content/images")
                data["src"] = final_image_path_for_ghost

                # If this image was the story's featured image, grab it.
                # Confusingly, post images ARE updated correctly in 2.0.3, so this path is different
                if "featured_image" in data:
                    del data["featured_image"]
                    feature_image = str(new_image_path).replace("exported_content_from_url", "")
                    encoded_content = encoded_content.replace(url, feature_image)
                else:
                    encoded_content = encoded_content.replace(url, final_image_path_for_ghost)
            else:
                # Delete medium statistic pixel.
                del mobiledoc_post["cards"][card_index]
                encoded_content = encoded_content.replace(url, '')

    # Create the final post dictionary as required by Ghost 2.0
    return {
        "id": post_index,
        "uuid": uuid,
        "title": title,
        "slug": slug,
        "type": "post",
        "canonical_url": canonical_url,
        "mobiledoc": json.dumps(mobiledoc_post),
        # "html": encoded_content,
        "comment_id": comment_id,
        "plaintext": plain_text,
        "feature_image": feature_image,
        "featured": 0,
        "page": 0,
        "status": status,
        "locale": None,
        "visibility": "public",
        "meta_title": None,
        "meta_description": None,
        "author_id": user,
        "created_at": created_at,
        "created_by": user,
        "updated_at": updated_at,
        "updated_by": user,
        "published_at": published_at,
        "published_by": user,
        "custom_excerpt": None,  # custom_excerpt,
        "codeinjection_head": None,
        "codeinjection_foot": None,
        "custom_template": None,

        # These all inherit from the metadata title/description in Ghost, so no need to set them explicitly
        "og_image": None,
        "og_title": None,
        "og_description": None,
        "twitter_image": None,
        "twitter_title": None,
        "twitter_description": None,
    }


def convert_downloaded_post_to_ghost_json(local_post_file, canonical_url, user, export_folder):
    logging.info(f"Parsing downloaded {local_post_file.name}")

    # Get the uuid from the original URL
    uuid = canonical_url.split("-")[-1]
    # Get the "slug" from the filename.
    slug = local_post_file.name.split(".")[0]
    # Assume everything is published as, well, it is.
    status = "published"

    with open(local_post_file) as post_content_wrapper:
        post_content = post_content_wrapper.read()
        soup = BeautifulSoup(post_content, 'html.parser')

        # - Guessing the first h1 is the Article Title...
        title = soup.find("h1").text
        if not title:
            title = "Empty title"
        # - ... and same with the Subtitle, guess first h2 it is...
        subtitle = soup.find("h2").text if soup.find("h2") else None


def convert_downloaded_post_to_ghost_json_old(html_filename, post_tuple, user):
    """
    Convert a Medium HTML export file's content into a Mobiledoc document.
    :param html_filename: The original filename from Medium (needed to grab publish state)
    :param post_tuple: Tuple with the html body (string) of the post itself & a post_index.
    :param user: ID of user to set posts to
    :return: Python dictionary representing a Mobiledoc version of this post
    """
    logging.info(f"Parsing downloaded {html_filename}")

    # Get the publish date and slug from the exported filename
    _, filename = html_filename.split("/")
    uuid, slug, date, status = parse_medium_filename(filename)

    post_html_content = post_tuple[0]
    post_index = post_tuple[1]

    # Extract post-level metadata elements that will be at known elements
    soup = BeautifulSoup(post_html_content, 'html.parser')

    # - Article Title
    title = soup.find("h1", {"class": "p-name"}).text
    if not title:
        title = "Empty title"
    # - Subtitle
    subtitle = soup.find("section", {"class": "p-summary"}).text if soup.find("section",
                                                                              {"class": "p-summary"}) else None

    # Canonical link
    canonical_link = None
    canonical_link_el = soup.find("a", {"class": "p-canonical"})
    if canonical_link_el is not None:
        canonical_link = canonical_link_el["href"]

    # Medium stores every comment as full story.
    # Guess if this post was a comment or a post based on if it has a post title h3 or not.
    # If it seems to be a comment, skip converting it since we have no idea what it was a comment on.
    title_el = soup.find("h3", {"class": "graf--title"})

    # Hack: Some really old Medium posts used h2 instead of h3 for the title element.
    if not title_el:
        title_el = soup.find("h2", {"class": "graf--title"})

    # If there's no title element, this document is probably a comment. Skip!
    if title_el is None:
        logging.warning(f"Skipping {html_filename} because it appears to be a Medium comment, not a post!")
        return None

    # All the remaining document-evel attributes we need to collect
    comment_id = None
    plain_text = None
    feature_image = None
    created_at = date
    updated_at = date
    published_at = date
    custom_excerpt = subtitle

    # Convert story body itself to mobiledoc format (As required by Ghost)
    # parser = MediumHTMLParser()
    # parser.feed(post_html_content)
    # mobiledoc_post = parser.convert()
    #
    # # Download all the story's images to local disk cache folder
    # for card in mobiledoc_post["cards"]:
    #     card_type = card[0]
    #     if card_type == "image":
    #         data = card[1]
    #         url = data["src"]
    #
    #         cache_folder = Path("exported_content") / "downloaded_images" / slug
    #         new_image_path = download_image_with_local_cache(url, cache_folder)
    #
    #         # TODO: Fix this when Ghost fixes https://github.com/TryGhost/Ghost/issues/9821
    #         # Ghost 2.0.3 has a bug where it doesn't update imported image paths, so manually add
    #         # /content/images.
    #         final_image_path_for_ghost = str(new_image_path).replace("exported_content", "/content/images")
    #         data["src"] = final_image_path_for_ghost
    #
    #         # If this image was the story's featured image, grab it.
    #         # Confusingly, post images ARE updated correctly in 2.0.3, so this path is different
    #         if "featured_image" in data:
    #             del data["featured_image"]
    #             feature_image = str(new_image_path).replace("exported_content", "")
    #
    # # Create the final post dictionary as required by Ghost 2.0
    # return {
    #     "id": post_index,
    #     "uuid": uuid,
    #     "title": title,
    #     "slug": slug,
    #     "canonical_url": canonical_link,
    #     "mobiledoc": json.dumps(mobiledoc_post),
    #     "html": post_html_content,
    #     "comment_id": comment_id,
    #     "plaintext": plain_text,
    #     "feature_image": feature_image,
    #     "featured": 0,
    #     "page": 0,
    #     "status": status,
    #     "locale": None,
    #     "visibility": "public",
    #     "meta_title": None,
    #     "meta_description": None,
    #     "author_id": user,
    #     "created_at": created_at,
    #     "created_by": user,
    #     "updated_at": updated_at,
    #     "updated_by":  user,
    #     "published_at": published_at,
    #     "published_by": user,
    #     "custom_excerpt": custom_excerpt,
    #     "codeinjection_head": None,
    #     "codeinjection_foot": None,
    #     "custom_template": None,
    #
    #     # These all inherit from the metadata title/description in Ghost, so no need to set them explicitly
    #     "og_image": None,
    #     "og_title": None,
    #     "og_description": None,
    #     "twitter_image": None,
    #     "twitter_title": None,
    #     "twitter_description": None,
    # }


if __name__ == "__main__":
    get_posts_from_medium()
