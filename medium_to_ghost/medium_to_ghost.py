import click
from pathlib import Path

from medium_to_ghost.medium_additional_parser import parse_tags
from medium_to_ghost.medium_post_parser import convert_medium_post_to_ghost_json
import time
import json
from zipfile import ZipFile
import logging
import sys
import shutil

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger('medium_to_ghost')


def create_ghost_import_zip():
    """
    Zip up exported content in ./exported_content folder. Writes out medium_export_for_ghost.zip to disk.
    :return: None
    """
    shutil.make_archive("medium_export_for_ghost", "zip", "exported_content", logger=logger)


def create_export_file(converted_posts, converted_tags, converted_posts_tags):
    """
    Create a Ghost import json from a list of Ghost post documents.
    :param converted_posts: Ghost formatted python docs.
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
                    "posts": converted_posts,
                    "tags": converted_tags,
                    "posts_tags": converted_posts_tags
                }
            }
        ]
    }


def update_export_file(json_output, converted_posts, converted_tags, converted_posts_tags):
    """
    Updates the existing Ghost import JSON, or falls back to create a new one.
    :param json_output: Ghost formatted python docs.
    :param converted_posts: Ghost formatted python docs.
    :param converted_tags: Ghost formatted tags.
    :param converted_posts_tags: Ghost formatted posts_tags.
    :return: A Dict representation of a ghost export file you can dump to json.
    """
    if "db" in json_output:
        json_output["db"][0]["data"]["posts"].extend(converted_posts)
        json_output["db"][0]["data"]["tags"] = converted_tags
        json_output["db"][0]["data"]["posts_tags"].extend(converted_posts_tags)
    else:
        logger.info(f"Export file not JSON compatible, creating new one!")
        return create_export_file(converted_posts, converted_tags, converted_posts_tags)
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

    for post_index, filename in enumerate(medium_zip.namelist(), start=1):
        if filename != "posts/" and filename.startswith("posts/"):
            data = extract_utf8_file_from_zip(medium_zip, filename)
            posts[filename] = (data, post_index + highest_post_id + 1)

    return posts, post_index + highest_post_id + 1


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

        existing_tags = []
        highest_post_id = 1
        json_output = {}

        if append and export_output.exists():
            try:
                existing_output = open(export_output, "r")
                json_output = json.load(existing_output)
                existing_tags = json_output["existing_tags"]
                highest_post_id = json_output["highest_post_id"]
            except:
                logger.info(f"Export file not JSON compatible, creating new one!")
                append = False

        # TODO: instead of highest_post_id & highest_tag_id, cache tags & read them from JSON or such
        #       also perhaps read users from user import file & add them to individual exports...
        with ZipFile(medium_export_zipfile) as medium_zip, open(export_output, "w") as output:
            # TODO: First extract the profile & parse the user.
            raw_profile = extract_utf8_file_from_zip(medium_zip, 'profile/profile.html')

            # Next extract posts.
            posts, post_index = extract_posts_from_zip(medium_zip, highest_post_id)
            exported_posts = parse_posts(posts, user)

            # Extract tags & align with posts.
            # TODO: read existing tags if appending.
            exported_tags, exported_posts_tags, all_tags = parse_tags(exported_posts, existing_tags)

            # Finally create or append export file.
            if append and export_output.exists():
                export_data = update_export_file(json_output, exported_posts, exported_tags, exported_posts_tags)
            else:
                export_data = create_export_file(exported_posts, exported_tags, exported_posts_tags)
            export_data["highest_post_id"] = post_index
            export_data["existing_tags"] = all_tags
            json.dump(export_data, output, indent=2)

        # Put everything in a zip file for Ghost
        create_ghost_import_zip()
        logger.info(f"Successfully created medium_export_for_ghost.zip. Upload this file to a Ghost 2.0+ instance!")
    else:
        print(f"Unable to find {medium_export_zipfile}.")
        exit(1)


if __name__ == "__main__":
    main()
