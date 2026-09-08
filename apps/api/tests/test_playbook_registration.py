import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.services.playbook_registration import RemotePlaybookInput,register_remote


class PlaybookRegistrationTests(unittest.TestCase):
    def test_canonical_repository_deduplicates(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                one,created=register_remote(db,RemotePlaybookInput(name='Test',repository_url='https://github.com/Owner/Repo.git',skill_path='skill/SKILL.md'))
                two,again=register_remote(db,RemotePlaybookInput(name='Another',repository_url='https://github.com/owner/repo/',skill_path='skill/SKILL.md'))
                self.assertTrue(created);self.assertFalse(again);self.assertEqual(one.id,two.id)
                self.assertIsNone(one.revision)
        finally:engine.dispose()

    def test_untrusted_repository_and_path_rejected(self):
        for url,path in [('https://localhost/repo','SKILL.md'),('https://user:token@github.com/a/b','SKILL.md'),('https://github.com/a/b','../SKILL.md'),('https://github.com/a/b','/SKILL.md')]:
            with self.subTest(url=url,path=path), self.assertRaises(ValueError):RemotePlaybookInput(name='Test',repository_url=url,skill_path=path)
