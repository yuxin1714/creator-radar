import unittest
from unittest.mock import patch
from datetime import timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.work import Work, Transcript, utcnow
from app.services import job_queue as queue
from app.services.task_recovery import recover_interrupted
import app.main  # Register all model tables.


class JobQueueTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.patch = patch.object(queue, 'SessionLocal', self.sessions)
        self.patch.start()
        with self.sessions() as db:
            work = Work(platform='douyin', external_id='queue-test', source_url='https://example.test')
            db.add(work); db.flush(); self.wid = work.id
            db.add(Transcript(work_id=self.wid, status='PENDING', text='Preserved original'))
            job = queue.enqueue(db, 'transcript', self.wid)
            db.commit(); self.jid = job.id

    def tearDown(self):
        self.patch.stop(); self.engine.dispose()

    def test_transaction_rollback_and_enqueue_idempotency(self):
        with self.sessions() as db:
            self.assertEqual(queue.enqueue(db, 'transcript', self.wid).id, self.jid)
            queue.enqueue(db, 'probe', 'rollback'); db.rollback()
        with self.sessions() as db:
            self.assertIsNone(db.scalar(select(queue.QueuedJob).where(queue.QueuedJob.target_id == 'rollback')))

    def test_broker_failure_preserves_request_and_lost_delivery_republishes(self):
        with patch('app.worker.celery_app.send_task', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): queue.publish_pending()
        with self.sessions() as db:
            job = db.get(queue.QueuedJob, self.jid); self.assertEqual(job.state, 'QUEUED')
            job.state = 'SENT'; job.updated_at = utcnow() - timedelta(minutes=2); db.commit()
        with patch('app.worker.celery_app.send_task') as send:
            queue.publish_pending(); self.assertEqual(send.call_count, 1)

    def test_duplicates_and_previous_attempt_never_invoke_provider(self):
        def complete(*args):
            with self.sessions() as db:
                db.scalar(select(Transcript)).status = 'COMPLETED'; db.commit()
        with patch.object(queue, 'invoke', side_effect=complete) as invoke:
            queue.execute_job(self.jid, 0); invoke.assert_not_called()
            queue.execute_job(self.jid, 1); queue.execute_job(self.jid, 1)
            self.assertEqual(invoke.call_count, 1)

    def test_worker_restart_preserves_pending_but_marks_started_failed(self):
        with self.sessions() as db:
            db.get(queue.QueuedJob, self.jid).state = 'SENT'; db.commit()
        queue.recover_worker()
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(Transcript)).status, 'PENDING')
            self.assertEqual(db.get(queue.QueuedJob, self.jid).state, 'QUEUED')
            db.get(queue.QueuedJob, self.jid).state = 'RUNNING'
            db.scalar(select(Transcript)).status = 'PROCESSING'; db.commit()
        queue.recover_worker()
        with self.sessions() as db:
            item = db.scalar(select(Transcript))
            self.assertEqual(item.status, 'FAILED'); self.assertEqual(item.text, 'Preserved original')
            self.assertEqual(db.get(queue.QueuedJob, self.jid).state, 'FAILED')
            item.status = 'PENDING'; job = queue.enqueue(db, 'transcript', self.wid)
            self.assertEqual(job.attempt, 2); db.commit()
        with patch.object(queue, 'invoke') as invoke:
            queue.execute_job(self.jid, 1); invoke.assert_not_called()

    def test_api_restart_does_not_interrupt_worker(self):
        with self.sessions() as db:
            item = db.scalar(select(Transcript)); item.status = 'PROCESSING'; db.commit()
            recover_interrupted(db, recover_jobs=False)
            self.assertEqual(item.status, 'PROCESSING')

    def test_retry_during_worker_finalization_rolls_back(self):
        with self.sessions() as db:
            db.get(queue.QueuedJob, self.jid).state = 'RUNNING'
            db.scalar(select(Transcript)).status = 'FAILED'; db.commit()
        with self.sessions() as db:
            db.scalar(select(Transcript)).status = 'PENDING'
            with self.assertRaises(queue.QueueBusy): queue.enqueue(db, 'transcript', self.wid)
            db.rollback()
            self.assertEqual(db.scalar(select(Transcript)).status, 'FAILED')

    def test_failure_does_not_leak_exception_and_cannot_leave_pending(self):
        with patch.object(queue, 'invoke', side_effect=RuntimeError('private-provider-details')):
            queue.execute_job(self.jid, 1)
        with self.sessions() as db:
            item = db.scalar(select(Transcript))
            self.assertEqual(item.status, 'FAILED')
            self.assertNotIn('private-provider-details', item.error_summary)
            self.assertEqual(db.get(queue.QueuedJob, self.jid).state, 'FAILED')
