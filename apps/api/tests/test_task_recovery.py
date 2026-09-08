import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.work import Work, Task, Transcript, Analysis, CreationProject, CreationGeneration
from app.services.task_recovery import recover_interrupted
from app.services import metadata_pipeline, transcript_pipeline, llm_analysis
from app.core.config import Settings
from app.providers.base import ProviderError
from sqlalchemy.orm import sessionmaker


class TaskRecoveryTests(unittest.TestCase):
    def test_running_tasks_cannot_execute_twice(self):
        engine=create_engine('sqlite://'); Base.metadata.create_all(engine)
        sessions=sessionmaker(engine,expire_on_commit=False)
        try:
            with sessions() as db:
                work=Work(platform='douyin',external_id='test',source_url='https://example.test')
                db.add(work);db.flush();wid=work.id
                task=Task(work_id=wid,status='RUNNING')
                db.add_all([task,Transcript(work_id=wid,status='PROCESSING'),Analysis(work_id=wid,status='PROCESSING')]);db.commit();tid=task.id
            settings=Settings()
            with patch.object(metadata_pipeline,'SessionLocal',sessions):
                with self.assertRaises(ProviderError) as raised:
                    metadata_pipeline.process_task(tid,settings)
                self.assertEqual(raised.exception.code,'task_running')
            with patch.object(transcript_pipeline,'SessionLocal',sessions),patch.object(transcript_pipeline,'download_media') as download:
                transcript_pipeline.process_transcript(wid,settings)
                download.assert_not_called()
            with patch.object(llm_analysis,'SessionLocal',sessions),patch.object(llm_analysis.urllib.request,'urlopen') as request:
                llm_analysis.process_analysis(wid,settings)
                request.assert_not_called()
        finally:engine.dispose()

    def test_recovery_preserves_completed_results_and_waiting_metadata(self):
        engine=create_engine('sqlite://'); Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                work=Work(platform='douyin',external_id='test',source_url='https://example.test')
                project=CreationProject(title='Test',body='Saved draft')
                db.add_all([work,project]);db.flush()
                waiting=Task(work_id=work.id,status='PENDING')
                active=Task(work_id=work.id,status='RUNNING')
                transcript=Transcript(work_id=work.id,status='COMPLETED',text='Saved text')
                analysis=Analysis(work_id=work.id,status='PROCESSING',result={'summary':'Previous result'})
                generation=CreationGeneration(project_id=project.id,status='PENDING',playbook_id='test')
                db.add_all([waiting,active,transcript,analysis,generation]);db.commit()
                self.assertEqual(recover_interrupted(db),3)
                self.assertEqual(waiting.status,'PENDING')
                self.assertEqual(transcript.status,'COMPLETED')
                self.assertEqual(analysis.result,{'summary':'Previous result'})
                self.assertEqual(project.body,'Saved draft')
                self.assertEqual(generation.status,'FAILED')
                self.assertEqual(recover_interrupted(db),0)
        finally:engine.dispose()
