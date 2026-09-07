import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import main
from app.db import Base
from app.models.work import PlaybookRevision, Work, Analysis, Transcript
from app.services.creation_generation import reference_context


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
        for language in ("en", "zh-en", "zh-CN"):
            main.update_creation_project(created["id"], main.CreationInput(title="Test", output_language=language, body="Updated"))
            reread = main.get_creation_project(created["id"])
            self.assertEqual(reread["output_language"], language)
            self.assertEqual(reread["body"], "Updated")

    def test_custom_rules_are_persisted(self):
        created = main.create_playbook(main.PlaybookInput(name="Test skill", rules=["Use verified facts"]))
        with self.sessions() as db:
            saved = db.scalar(select(PlaybookRevision).where(PlaybookRevision.source_id == created["id"]))
            self.assertIsNotNone(saved)
            self.assertIn("Use verified facts", saved.content)

    def test_reference_survives_edit_and_loads_only_completed_material(self):
        with self.sessions() as db:
            work = Work(platform="douyin", external_id="test", source_url="https://www.douyin.com/video/test")
            db.add(work); db.commit()
            work_id = work.id
            db.add(Transcript(work_id=work_id, status="COMPLETED", text="Source text"))
            db.add(Analysis(work_id=work_id, status="FAILED", result={"summary": "stale"}))
            db.commit()
        created = main.create_creation_project(main.CreationInput(title="Test", work_id=work_id))
        edited = main.update_creation_project(created["id"], main.CreationInput(title="New title"))
        self.assertEqual(edited["work_id"], work_id)
        self.assertEqual(edited["context_type"], "work")
        with self.sessions() as db:
            from app.models.work import CreationProject
            reference = reference_context(db, db.get(CreationProject, created["id"]))
            self.assertEqual(reference["transcript"], "Source text")
            self.assertIsNone(reference["analysis"])

    def test_foreign_reference_is_rejected(self):
        with self.sessions() as db:
            work = Work(owner_id="someone-else", platform="douyin", external_id="test", source_url="https://www.douyin.com/video/test")
            db.add(work); db.commit()
            work_id = work.id
        response = main.create_creation_project(main.CreationInput(work_id=work_id))
        self.assertEqual(response.status_code, 404)

    def test_versions_preserve_original_and_skip_duplicate_saves(self):
        created = main.create_creation_project(main.CreationInput(title="Original", body="First"))
        project_id = created["id"]
        update = main.CreationInput(title="Edited", body="Second", output_language="en")
        main.update_creation_project(project_id, update)
        main.update_creation_project(project_id, update)
        versions = main.list_creation_versions(project_id)
        self.assertEqual([v["version_number"] for v in versions], [2, 1])
        self.assertEqual(versions[1]["snapshot"]["body"], "First")
        self.assertEqual(versions[0]["snapshot"]["output_language"], "en")
        main.update_creation_project(project_id, main.CreationInput(title="Original", body="First"))
        self.assertEqual(len(main.list_creation_versions(project_id)), 3)

    def test_version_read_checks_owner(self):
        from app.models.work import CreationProject
        with self.sessions() as db:
            item = CreationProject(owner_id="other", title="Private")
            db.add(item); db.commit(); project_id = item.id
        self.assertEqual(main.list_creation_versions(project_id).status_code, 404)
