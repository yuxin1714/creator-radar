import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main
from app.db import Base
from app.models.work import CreationGeneration
from app.services.generation_workflow import prepare_generation,GenerationOptions
from app.providers.base import ProviderError


class ProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        self.override=patch.object(main,'SessionLocal',self.sessions);self.override.start()
        self.project=main.create_creation_project(main.CreationInput(title='Lifecycle',body='Saved draft'))

    def tearDown(self):self.override.stop();self.engine.dispose()

    def change(self,status):
        current=main.get_creation_project(self.project['id'])
        return main.update_project_status(self.project['id'],main.ProjectStatusInput(status=status,expected_updated_at=datetime.fromisoformat(current['updated_at'])))

    def test_complete_archive_restore_preserves_draft_and_blocks_writes(self):
        self.assertEqual(self.change('COMPLETED')['status'],'COMPLETED')
        self.assertEqual(self.change('ARCHIVED')['status'],'ARCHIVED')
        self.assertEqual(main.update_creation_project(self.project['id'],main.CreationInput(body='Overwrite')).status_code,409)
        with self.sessions() as db:
            with self.assertRaises(ProviderError):prepare_generation(db,self.project['id'],GenerationOptions(),main.settings)
        self.assertEqual(main.get_creation_project(self.project['id'])['body'],'Saved draft')
        self.assertEqual(self.change('DRAFT')['status'],'DRAFT')
        self.change('COMPLETED')
        edited=main.update_creation_project(self.project['id'],main.CreationInput(title='Edited',body='Revision'))
        self.assertEqual(edited['status'],'DRAFT')

    def test_active_generation_blocks_archive_and_stale_status_request_fails(self):
        original=self.project['updated_at'];self.change('COMPLETED')
        stale=main.update_project_status(self.project['id'],main.ProjectStatusInput(status='ARCHIVED',expected_updated_at=datetime.fromisoformat(original)))
        self.assertEqual(stale.status_code,409)
        with self.sessions() as db:db.add(CreationGeneration(project_id=self.project['id'],playbook_id='structure-borrowing-v1',status='PROCESSING'));db.commit()
        self.assertEqual(self.change('ARCHIVED').status_code,409)
