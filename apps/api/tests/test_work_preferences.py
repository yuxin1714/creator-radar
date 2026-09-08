import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.work import Work
from app.services.work_preferences import save_preferences, PreferencesInput
from app.providers.base import ProviderError


class WorkPreferencesTests(unittest.TestCase):
    def test_preferences_persist_and_stale_or_foreign_writes_fail(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                work=Work(platform='douyin',external_id='1',source_url='https://example.test')
                db.add(work);db.commit();wid=work.id
                body=PreferencesInput(favorite=True,archived=True,tags=[' Story ','Story','Video'],expected_revision=0)
                saved=save_preferences(db,wid,body)
                self.assertEqual(saved['tags'],['Story','Video']);self.assertEqual(saved['revision'],1)
                with self.assertRaises(ProviderError):save_preferences(db,wid,body)
                restored=save_preferences(db,wid,PreferencesInput(favorite=True,archived=False,tags=[],expected_revision=1))
                self.assertFalse(restored['archived']);self.assertIsNotNone(db.get(Work,wid))
                work.owner_id='other';db.commit()
                with self.assertRaises(ProviderError):save_preferences(db,wid,PreferencesInput(favorite=False,archived=False,tags=[],expected_revision=2))
        finally:engine.dispose()

    def test_long_tags_rejected(self):
        with self.assertRaises(ValueError):PreferencesInput(favorite=False,archived=False,tags=['a'*31],expected_revision=0)
