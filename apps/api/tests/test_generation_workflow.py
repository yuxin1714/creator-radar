import io
import json
import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.core.config import Settings
from app.models.work import CreationProject, CreationBrief, CreationGeneration, GenerationInput
from app.services.generation_workflow import GenerationOptions, prepare_generation
from app.services import creation_generation as worker
from app.providers.base import ProviderError


class GenerationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.settings = Settings(llm_base_url="https://example.test", llm_api_key="test", llm_model="test")
        with self.sessions() as db:
            p = CreationProject(title="Original", body="Keep draft")
            db.add(p); db.flush()
            self.project_id = p.id
            db.add(CreationBrief(project_id=p.id)); db.commit()

    def tearDown(self):
        self.engine.dispose()

    def prepare(self):
        with self.sessions() as db:
            item = prepare_generation(db, self.project_id, GenerationOptions(mode="directions"), self.settings)
            db.commit()
            return item.id

    def test_duplicate_and_invalid_selection_rejected(self):
        with self.sessions() as db:
            with self.assertRaises(ProviderError):
                prepare_generation(db, self.project_id, GenerationOptions(direction_generation_id="foreign", direction_index=0), self.settings)
        self.prepare()
        with self.sessions() as db:
            with self.assertRaises(ProviderError) as raised:
                prepare_generation(db, self.project_id, GenerationOptions(), self.settings)
            self.assertEqual(raised.exception.code, "generation_running")

    def test_frozen_context_and_selected_direction(self):
        gid = self.prepare()
        content = json.dumps({"directions":[{"title":str(i),"premise":"Premise","hook":"Hook","outline":["Start","End"]} for i in range(3)]})
        with self.sessions() as db:
            db.get(CreationProject, self.project_id).title = "Changed"
            db.commit()
        response = io.StringIO(json.dumps({"choices":[{"message":{"content":content}}]}))
        with patch.object(worker, "SessionLocal", self.sessions), patch.object(worker.urllib.request, "urlopen", return_value=response) as call:
            worker.generate(self.project_id, gid, self.settings)
            prompt = json.loads(call.call_args.args[0].data)["messages"][1]["content"]
            self.assertIn('"title": "Original"', prompt)
            self.assertNotIn('"title": "Changed"', prompt)
            worker.generate(self.project_id, gid, self.settings)
            self.assertEqual(call.call_count, 1)
        with self.sessions() as db:
            self.assertEqual(db.get(CreationGeneration, gid).status, "COMPLETED")
            chosen = prepare_generation(db, self.project_id, GenerationOptions(direction_generation_id=gid, direction_index=1), self.settings)
            frozen = db.get(GenerationInput, chosen.id)
            self.assertEqual(frozen.context["selected_direction"]["title"], "1")
            self.assertEqual(frozen.context["title"], "Original")
            self.assertEqual(db.get(CreationProject, self.project_id).body, "Keep draft")

    def test_invalid_model_directions_fail_without_overwriting_draft(self):
        gid = self.prepare()
        response = io.StringIO(json.dumps({"choices":[{"message":{"content":'{"directions":[]}'}}]}))
        with patch.object(worker, "SessionLocal", self.sessions), patch.object(worker.urllib.request, "urlopen", return_value=response):
            worker.generate(self.project_id, gid, self.settings)
        with self.sessions() as db:
            self.assertEqual(db.get(CreationGeneration, gid).status, "FAILED")
            self.assertEqual(db.get(CreationProject, self.project_id).body, "Keep draft")

    def test_refinement_requires_feedback_and_freezes_current_draft(self):
        with self.sessions() as db:
            with self.assertRaises(ProviderError):
                prepare_generation(db, self.project_id, GenerationOptions(mode="refine", feedback="  "), self.settings)
            item = prepare_generation(db, self.project_id, GenerationOptions(mode="refine", feedback="Shorter opening"), self.settings)
            gid = item.id
            db.commit()
            db.get(CreationProject, self.project_id).body = "Later edit"
            db.commit()
        response = io.StringIO(json.dumps({"choices":[{"message":{"content":"Revised draft"}}]}))
        with patch.object(worker, "SessionLocal", self.sessions), patch.object(worker.urllib.request, "urlopen", return_value=response) as call:
            worker.generate(self.project_id, gid, self.settings)
            prompt = json.loads(call.call_args.args[0].data)["messages"][1]["content"]
            self.assertIn("Shorter opening", prompt)
            self.assertIn("Keep draft", prompt)
            self.assertNotIn("Later edit", prompt)
        with self.sessions() as db:
            self.assertEqual(db.get(CreationGeneration, gid).content, "Revised draft")
            self.assertEqual(db.get(CreationProject, self.project_id).body, "Later edit")
