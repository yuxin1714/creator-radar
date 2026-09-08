import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import main
from app.db import Base
from app.models.work import Work,CreationProject,CreationVersion,CreationGeneration,Task
from app.services.pagination import paginated
from fastapi import HTTPException


class PaginationTests(unittest.TestCase):
    def test_old_records_and_matches_beyond_first_page_remain_accessible(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine);sessions=sessionmaker(engine,expire_on_commit=False)
        try:
            with sessions() as db:
                for i in range(55):db.add(Work(platform='douyin',external_id=str(i),title='Find this' if i==0 else 'Ordinary',source_url='https://example.test'))
                db.add(Work(platform='douyin',external_id='private',owner_id='other',source_url='https://example.test'))
                project=CreationProject(title='History');db.add(project);db.flush();pid=project.id
                work=db.query(Work).filter_by(external_id='0').first()
                for i in range(61):db.add(CreationVersion(project_id=pid,version_number=i+1,snapshot={'body':str(i)}));db.add(CreationGeneration(project_id=pid,playbook_id='test',content=str(i)))
                for i in range(205):db.add(Task(work_id=work.id))
                db.commit()
            with patch.object(main,'SessionLocal',sessions):
                first=main.list_works(page=1);last=main.list_works(page=3)
                self.assertEqual(first['total'],55);self.assertEqual(len(last['items']),15)
                self.assertEqual(main.list_works(page=1,q='Find this')['total'],1)
                history=main.list_creation_versions(pid,page=4)
                self.assertEqual(history['total'],61);self.assertEqual(history['items'][0]['version_number'],1)
                self.assertEqual(main.list_creation_generations(pid,page=4)['total'],61)
                self.assertGreater(main.list_tasks(page=11)['total'],200)
        finally:engine.dispose()

    def test_bounds_and_empty_page(self):
        self.assertEqual(paginated([],99)['page'],1)
        for page,size in [(0,20),(1,0),(1,101)]:
            with self.assertRaises(HTTPException):paginated([1],page,size)
