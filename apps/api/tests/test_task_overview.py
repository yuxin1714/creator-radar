import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.work import Work, Task, Transcript, Analysis, CreationProject, CreationGeneration, GenerationInput
from app.services.task_overview import task_overview


class TaskOverviewTests(unittest.TestCase):
    def test_aggregates_real_stages_and_excludes_other_owner(self):
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                work = Work(platform='douyin', external_id='test', source_url='https://example.test')
                private = Work(owner_id='other', platform='douyin', external_id='private', source_url='https://example.test')
                project = CreationProject(title='Draft')
                foreign = CreationProject(title='Private', owner_id='other')
                db.add_all([work, private, project, foreign]); db.flush()
                gen = CreationGeneration(project_id=project.id, status='PROCESSING', playbook_id='test')
                db.add_all([Task(work_id=work.id), Transcript(work_id=work.id, status='COMPLETED'), Analysis(work_id=work.id, status='FAILED', error_summary='Analysis failed'), Task(work_id=private.id), CreationGeneration(project_id=foreign.id, playbook_id='test'), gen]); db.flush()
                db.add(GenerationInput(generation_id=gen.id, mode='refine', context={}, model='test')); db.commit()
                items = task_overview(db)
                self.assertEqual(len(items), 4)
                self.assertEqual({item['kind'] for item in items}, {'metadata','transcript','analysis','creation'})
                creation = next(item for item in items if item['kind']=='creation')
                self.assertEqual(creation['stage'], 'refine')
                self.assertEqual(creation['status'], 'PROCESSING')
                self.assertEqual(creation['href'], '/creation/'+project.id+'?generation='+gen.id)
                analysis = next(item for item in items if item['kind']=='analysis')
                self.assertEqual(analysis['error_summary'], 'Analysis failed')
                self.assertTrue(analysis['href'].endswith('?tab=analysis'))
        finally:
            engine.dispose()
