import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import main
from app.db import Base
from app.models.work import PlaybookRevision


class CreationApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.override = patch.object(main, "SessionLocal", self.sessions)
        self.override.start()

    def tearDown(self):
        self.override.stop()
        self.engine.dispose()

    def test_project_language_and_body_survive_save(self):
        created = main.create_creation_project(main.CreationInput(title="Test", output_language="en", body="Draft"))
        read = main.get_creation_project(created["id"])
        self.assertEqual(read["output_language"], "en")
        self.assertEqual(read["body"], "Draft")

    def test_custom_rules_are_persisted(self):
        created = main.create_playbook(main.PlaybookInput(name="Test skill", rules=["Use verified facts"]))
        with self.sessions() as db:
            saved = db.scalar(select(PlaybookRevision).where(PlaybookRevision.source_id == created["id"]))
            self.assertIsNotNone(saved)
            self.assertIn("Use verified facts", saved.content)
