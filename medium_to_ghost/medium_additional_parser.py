import logging
from bs4 import BeautifulSoup
import urllib.request
from urllib.error import HTTPError
import re


def parse_tags(exported_posts, highest_tag_id):
    """
    Parse a list of exported posts' canonical urls for Tags
    :param exported_posts: List of parsed Ghost posts.
    :param highest_tag_id: List of parsed Ghost posts.
    :return: Ghost versions of all tags & all post tags.
    """
    all_posts_tags = []
    all_tags = []

    for post in exported_posts:
        if post["canonical_url"] is not None:
            post_tags = parse_tags_from_canonical_url(post["canonical_url"], post["id"], all_tags, highest_tag_id)
            if post_tags is not None:
                all_posts_tags.extend(post_tags)

    converted_tags = convert_all_tags(all_tags, highest_tag_id)
    return converted_tags, all_posts_tags


def parse_tags_from_canonical_url(canonical_url, post_id, all_tags, highest_tag_id):
    """
    Parse a canonical_url for Tags.
    :param canonical_url: Canonical URL of medium post.
    :param post_id: ID of POST as created.
    :param all_tags: List of all currently available tags.
    :param highest_tag_id:
    :return: Ghost versions of all tags & all post tags.
    """
    post_tags = []

    # Send a User Agent so Medium doesn't return 403
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'medium_to_ghost post exporter')]
    urllib.request.install_opener(opener)

    logging.info(f"Downloading {canonical_url} and parsing tags.")

    try:
        response = urllib.request.urlopen(canonical_url)
        post_content = response.read()

        soup = BeautifulSoup(post_content, 'html.parser')
        tagged_anchors = soup.find_all(href=re.compile("tagged"))
        for anchor in tagged_anchors:
            if anchor.contents[0] not in all_tags:
                all_tags.append(anchor.contents[0])
            post_tag = {
                "tag_id": all_tags.index(anchor.contents[0]) + highest_tag_id,
                "post_id": post_id
            }
            post_tags.append(post_tag)
    except HTTPError as e:
        logging.error(f"Download failed for {canonical_url}. Error Message: {e.msg}")

    return post_tags


def convert_all_tags(all_tags, highest_tag_id):
    """
    Converts all_tags to Ghost format.
    :param all_tags: List of all currently available tags.
    :param highest_tag_id: .
    :return: Ghost versions of all_tags
    """
    converted_tags = []
    
    for tag_id, tag_name in enumerate(all_tags):
        ghost_tag = {
            "id":           tag_id + highest_tag_id,
            "name":         tag_name,
            "description":  ""
        }
        converted_tags.append(ghost_tag)
    
    return converted_tags
