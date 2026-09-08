import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.work import PlaybookSource,utcnow
from app.services import skill_updates
from app.services.remote_playbooks import sync_playbook,_sync_locks
from app.providers.base import ProviderError
import threading


class SkillUpdateTests(unittest.TestCase):
    def test_schedule_checks_once_and_keeps_old_revision_on_failure(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine);sessions=sessionmaker(engine,expire_on_commit=False)
        try:
            with sessions() as db:
                db.add(PlaybookSource(id='test-auto',name='Test',source_type='remote',revision='old'));db.flush();db.add(skill_updates.SkillUpdatePolicy(source_id='test-auto',enabled=True));db.commit()
            with patch.object(skill_updates,'SessionLocal',sessions),patch.object(skill_updates,'sync_playbook',return_value={'updated':False}) as sync:
                skill_updates.check_due_skills();skill_updates.check_due_skills();self.assertEqual(sync.call_count,1)
                with sessions() as db:
                    policy=db.get(skill_updates.SkillUpdatePolicy,'test-auto');self.assertEqual(policy.status,'CURRENT');policy.next_check_at=utcnow();db.commit()
                sync.side_effect=ProviderError('playbook_sync_failed','Unavailable')
                skill_updates.check_due_skills()
                with sessions() as db:
                    self.assertEqual(db.get(PlaybookSource,'test-auto').revision,'old')
                    self.assertEqual(db.get(skill_updates.SkillUpdatePolicy,'test-auto').status,'FAILED')
        finally:engine.dispose()

    def test_same_source_cannot_sync_twice_at_once(self):
        lock=threading.Lock();lock.acquire();_sync_locks['locked-test']=lock
        try:
            with self.assertRaises(ProviderError) as error:sync_playbook('locked-test')
            self.assertEqual(error.exception.code,'playbook_sync_running')
        finally:lock.release();_sync_locks.pop('locked-test')
