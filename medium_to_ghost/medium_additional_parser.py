import logging
from pathlib import Path
from bs4 import BeautifulSoup
import re

from medium_to_ghost.mtg_utils import download_with_local_cache


def parse_tags(exported_posts, existing_tags):
    """
    Parse a list of exported posts' canonical urls for Tags
    :param exported_posts: List of parsed Ghost posts.
    :param existing_tags: Already loaded tags or empty.
    :return: Ghost versions of all tags & all post tags + all_tags combined.
    """
    all_posts_tags = []
    all_tags = existing_tags

    for post in exported_posts:
        if post["canonical_url"] is not None:
            post_tags = parse_tags_from_canonical_url(post["canonical_url"], post["id"], all_tags)
            if post_tags is not None:
                all_posts_tags.extend(post_tags)

    converted_tags = convert_all_tags(all_tags)
    return converted_tags, all_posts_tags, all_tags


def post_filename_creator(uri):
    slug_parts = uri.split("-")
    slug = "-".join(slug_parts[0:-1])
    slug += '.html'
    return slug


def parse_tags_from_canonical_url(canonical_url, post_id, all_tags):
    """
    Parse a canonical_url for Tags.
    :param canonical_url: Canonical URL of medium post.
    :param post_id: ID of POST as created.
    :param all_tags: List of all currently available tags.
    :return: Ghost versions of all tags & all post tags.
    """
    post_tags = []

    logging.info(f"Downloading {canonical_url} and parsing tags.")

    cache_folder = Path("exported_content") / "downloaded_posts"
    local_post_file = download_with_local_cache(canonical_url, cache_folder, post_filename_creator)

    with open(local_post_file) as post_content_wrapper:
        post_content = post_content_wrapper.read()
        soup = BeautifulSoup(post_content, 'html.parser')
        tagged_anchors = soup.find_all(href=re.compile("tagged"))
        for anchor in tagged_anchors:
            if anchor.contents[0] not in all_tags:
                all_tags.append(anchor.contents[0])
            post_tag = {
                "tag_id": all_tags.index(anchor.contents[0]),
                "post_id": post_id
            }
            post_tags.append(post_tag)

    return post_tags


def convert_all_tags(all_tags):
    """
    Converts all_tags to Ghost format.
    :param all_tags: List of all currently available tags.
    :return: Ghost versions of all_tags
    """
    converted_tags = []
    
    for tag_id, tag_name in enumerate(all_tags):
        ghost_tag = {
            "id":           tag_id,
            "name":         tag_name,
            "description":  ""
        }
        converted_tags.append(ghost_tag)
    
    return converted_tags
