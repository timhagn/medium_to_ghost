import click
from pathlib import Path

from medium_to_ghost.medium_additional_parser import parse_tags, parse_user
from medium_to_ghost.medium_post_parser import convert_medium_post_to_ghost_json
import time
import json
from zipfile import ZipFile
import logging
import sys
import shutil

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger('medium_to_ghost')


def create_ghost_import_zip(name):
    """
    Zip up exported content in ./exported_content folder. Writes out medium_export_for_ghost.zip to disk.
    :return: None
    """
    shutil.make_archive("medium_export_for_ghost", "zip", name or "exported_content", logger=logger)


def create_export_file(converted_user, converted_posts, converted_tags, converted_posts_tags):
    """
    Create a Ghost import json from a list of Ghost post documents.
    :param converted_user: User in Ghost format.
    :param converted_posts: Posts in Ghost format.
    :param converted_tags: Ghost formatted tags.
    :param converted_posts_tags: Ghost formatted posts_tags.
    :return: A Dict representation of a ghost export file you can dump to json.
    """
    return {
        "db": [
            {
                "meta": {
                    "exported_on": int(time.time()),
                    "version": "2.18.3"
                },
                "data": {
                    "users": [converted_user],
                    "posts": converted_posts,
                    "tags": converted_tags,
                    "posts_tags": converted_posts_tags
                }
            }
        ]
    }


def update_or_create_export_file(json_output, converted_user, converted_posts, converted_tags, converted_posts_tags):
    """
    Updates the existing Ghost import JSON, or falls back to create a new one.
    :param json_output: Current Ghost JSON output or empty dict.
    :param converted_user: User in Ghost format.
    :param converted_posts: Posts in Ghost format.
    :param converted_tags: Ghost formatted tags.
    :param converted_posts_tags: Ghost formatted posts_tags.
    :return: A Dict representation of a ghost export file you can dump to json.
    """
    if "db" in json_output:
        json_output["db"][0]["data"]["users"].extend([converted_user])
        json_output["db"][0]["data"]["posts"].extend(converted_posts)
        json_output["db"][0]["data"]["tags"] = converted_tags
        json_output["db"][0]["data"]["posts_tags"].extend(converted_posts_tags)
    else:
        logger.info(f"Export file not JSON compatible, creating new one!")
        return create_export_file(converted_user, converted_posts, converted_tags, converted_posts_tags)
    return json_output


def parse_posts(posts, user):
    """
    Parse a list of Medium HTML posts
    :param posts: List of medium posts as dict with filename: (html_content, post_index)
    :param user: ID of user
    :return: Ghost versions of those same posts
    """
    converted_posts = []

    for name, post_tuple in posts.items():
        converted_post = convert_medium_post_to_ghost_json(name, post_tuple, user)
        if converted_post is not None:
            converted_posts.append(converted_post)

    return converted_posts


def extract_utf8_file_from_zip(zip, filename):
    """
    Python's zip library returns bytes, not unicode strings. So we need to
    convert Medium posts into utf-8 manually before we parse them.
    :param zip: Medium export zip file
    :param filename: post export filename to pull out as utf-8
    :return: utf-8 string data for a file
    """
    with zip.open(filename) as file:
        data = file.read().decode('utf8')

    return data


def extract_posts_from_zip(medium_zip, highest_post_id):
    """
    Extract all Medium posts from the Medium export Zip file as utf-8 strings
    :param medium_zip: zip file from Medium
    :param highest_post_id: ID of highest existing post
    :return: list of posts as a dict with filename: (data, post_index), post_index
    """
    posts = {}
    post_index = 1

    for filename in medium_zip.namelist():
        if filename != "posts/" and filename.startswith("posts/"):
            data = extract_utf8_file_from_zip(medium_zip, filename)
            posts[filename] = (data, post_index + highest_post_id)
            post_index += 1

    return posts, post_index + highest_post_id - 1


@click.command()
@click.option('-u', '--user', 'user', default=1, help='ID of user to set posts to.', show_default=True)
@click.option('-a', '--append', 'append', is_flag=True, help='Shall new content be added to existing?')
@click.argument('medium_export_zipfile')
def main(medium_export_zipfile, user, append):
    export_folder = Path("exported_content")
    if Path(medium_export_zipfile).exists():
        export_folder.mkdir(parents=True, exist_ok=True)
        export_file = "medium_export_for_ghost.json"
        export_output = export_folder / export_file
        config_file = "mtg_conf.json"
        config_output = export_folder / config_file

        existing_tags = []
        highest_post_id = 0
        json_output = {}

        if append and config_output.exists():
            try:
                existing_config = open(config_output, "r")
                config = json.load(existing_config)
                existing_tags = config["existing_tags"]
                highest_post_id = config["highest_post_id"]
                existing_output = open(export_output, "r")
                json_output = json.load(existing_output)
            except:
                logger.info(f"Export file not JSON compatible, creating new one!")

        with ZipFile(medium_export_zipfile) as medium_zip, open(export_output, "w") as output:
            # TODO: First extract the profile & parse the user.
            raw_profile = extract_utf8_file_from_zip(medium_zip, 'profile/profile.html')
            exported_user = parse_user(raw_profile, user)

            # Next extract posts.
            posts, post_index = extract_posts_from_zip(medium_zip, highest_post_id)
            exported_posts = parse_posts(posts, user)

            # Extract tags & align with posts.
            exported_tags, exported_posts_tags, all_tags = parse_tags(exported_posts, existing_tags)

            # Finally create or append export file.
            export_data = update_or_create_export_file(json_output, exported_user, exported_posts, exported_tags,
                                                       exported_posts_tags)
            json.dump(export_data, output, indent=2)

            config_data = {
                "highest_post_id": post_index,
                "existing_tags": all_tags,
            }
            config_file = open(config_output, "w")
            json.dump(config_data, config_file, indent=2)

        # Put everything in a zip file for Ghost
        create_ghost_import_zip()
        logger.info(f"Successfully created medium_export_for_ghost.zip. Upload this file to a Ghost 2.0+ instance!")
    else:
        print(f"Unable to find {medium_export_zipfile}.")
        exit(1)


if __name__ == "__main__":
    main()
