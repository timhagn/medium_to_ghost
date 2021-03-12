import unittest
import os
from pathlib import Path
from medium_to_ghost import medium_post_parser
import json


class TestMediumPostParser(unittest.TestCase):

    def test_parse_medium_filename_posted(self):
        filename = "2016-06-13_Machine-Learning-is-Fun--Part-3--Deep-Learning-and-Convolutional-Neural-Networks-f40359318721.html"

        uuid, slug, date, status = medium_post_parser.parse_medium_filename(filename)

        self.assertEqual(uuid, "f40359318721")
        self.assertEqual(slug, "Machine-Learning-is-Fun--Part-3--Deep-Learning-and-Convolutional-Neural-Networks")
        self.assertEqual(date, "2016-06-13")
        self.assertEqual(status, "published")

    def test_parse_medium_filename_draft(self):
        filename = "draft_test-7e48eb14931e.html"

        uuid, slug, date, status = medium_post_parser.parse_medium_filename(filename)

        self.assertEqual(uuid, "7e48eb14931e")
        self.assertEqual(slug, "test")
        self.assertIsNone(date)
        self.assertEqual(status, "draft")

    def test_MediumHTMLParser(self):
        doc = Path(os.path.join(os.path.dirname(__file__), 'test_data', 'draft_test-7e48eb14931e.html'))
        html = doc.read_text()

        expected_doc = Path(os.path.join(os.path.dirname(__file__), 'test_data', 'draft_test_parsed.json'))
        expected_json = expected_doc.read_text()

        parser = medium_post_parser.MediumHTMLParser()
        parser.feed(html)
        mobiledoc = parser.convert()

        result = json.dumps(mobiledoc, indent=2)
        self.assertEqual(result, expected_json)

    def test_convert_medium_post_to_ghost_json(self):
        doc = Path(os.path.join(os.path.dirname(__file__), 'test_data', 'draft_test-7e48eb14931e.html'))
        html = doc.read_text()
        testuser = 1
        post_tuple = (html, 0)


        expected_mobiledoc = Path(os.path.join(os.path.dirname(__file__), 'test_data', 'draft_test_mobiledoc.json'))
        expected_json = expected_mobiledoc.read_text()

        result = medium_post_parser.convert_medium_post_to_ghost_json("posts/draft_test-7e48eb14931e.html", post_tuple,
                                                                      testuser)

        self.assertEqual(result["uuid"], "7e48eb14931e")
        self.assertEqual(result["title"], "Post Title")
        self.assertEqual(result["slug"], "test")
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["mobiledoc"], expected_json)
