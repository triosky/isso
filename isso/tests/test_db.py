
try:
    import unittest2 as unittest
except ImportError:
    import unittest

import os
import sqlite3
import tempfile

from isso.db import SQLite3
from isso.core import Config

from isso.compat import iteritems


class TestDBMigration(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp()

    def tearDown(self):
        os.unlink(self.path)

    def test_defaults(self):

        db = SQLite3(self.path, Config.load(None))

        self.assertEqual(db.version, SQLite3.MAX_VERSION)
        self.assertTrue(db.preferences.get("session-key", "").isalnum())

    def test_session_key_migration(self):

        conf = Config.load(None)
        conf.set("general", "session-key", "supersecretkey")

        with sqlite3.connect(self.path) as con:
            con.execute("PRAGMA user_version = 1")
            con.execute("CREATE TABLE threads (id INTEGER PRIMARY KEY)")

        db = SQLite3(self.path, conf)

        self.assertEqual(db.version, SQLite3.MAX_VERSION)
        self.assertEqual(db.preferences.get("session-key"),
                         conf.get("general", "session-key"))

        # try again, now with the session-key removed from our conf
        conf.remove_option("general", "session-key")
        db = SQLite3(self.path, conf)

        self.assertEqual(db.version, SQLite3.MAX_VERSION)
        self.assertEqual(db.preferences.get("session-key"),
                         "supersecretkey")

    def test_limit_nested_comments(self):

        tree = {
            1: None,
            2: None,
               3: 2,
                  4: 3,
                  7: 3,
               5: 2,
            6: None
        }

        with sqlite3.connect(self.path) as con:
            con.execute("PRAGMA user_version = 2")
            con.execute("CREATE TABLE threads ("
                        "    id INTEGER PRIMARY KEY,"
                        "    uri VARCHAR UNIQUE,"
                        "    title VARCHAR)")
            con.execute("CREATE TABLE comments ("
                        "    tid REFERENCES threads(id),"
                        "    id INTEGER PRIMARY KEY,"
                        "    parent INTEGER,"
                        "    created FLOAT NOT NULL, modified FLOAT,"
                        "    text VARCHAR, email VARCHAR, website VARCHAR,"
                        "    mode INTEGER,"
                        "    remote_addr VARCHAR,"
                        "    likes INTEGER DEFAULT 0,"
                        "    dislikes INTEGER DEFAULT 0,"
                        "    voters BLOB)")

            con.execute("INSERT INTO threads (uri, title) VALUES (?, ?)", ("/", "Test"))
            for (id, parent) in iteritems(tree):
                con.execute("INSERT INTO comments ("
                            "   tid, parent, created)"
                            "VALUEs (?, ?, ?)", (id, parent, id))

        conf = Config.load(None)
        SQLite3(self.path, conf)

        flattened = [
            (1, None),
            (2, None),
            (3, 2),
            (4, 2),
            (5, 2),
            (6, None),
            (7, 2)
        ]

        with sqlite3.connect(self.path) as con:
            rv = con.execute("SELECT id, parent FROM comments ORDER BY created").fetchall()
            self.assertEqual(flattened, rv)
