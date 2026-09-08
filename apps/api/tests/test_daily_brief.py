import unittest
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.work import Work,Transcript,Analysis,utcnow
from app.models.work_preferences import WorkPreferences
from app.services.daily_brief import daily_brief


class DailyBriefTests(unittest.TestCase):
    def test_only_recent_owned_unarchived_verified_material_can_be_selected(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine);now=utcnow()
        try:
            with Session(engine) as db:
                for i in range(11):
                    work=Work(platform='douyin',external_id=str(i),source_url='https://example.test',owner_id='other' if i==10 else 'local-user',created_at=now-timedelta(days=10 if i==8 else 1))
                    db.add(work);db.flush()
                    db.add(Transcript(work_id=work.id,status='COMPLETED',text='真实原文'))
                    result={'summary':'Summary','hook':'Hook','structure':['Structure'],'key_points':['Point'],'content_score':50+i,'score_reasons':['Reason'],'evidence':[{'claim':'Claim','quote':'伪造引用' if i==7 else '真实原文'}]}
                    db.add(Analysis(work_id=work.id,status='COMPLETED',result=result))
                    if i==9:db.add(WorkPreferences(work_id=work.id,archived=True))
                db.commit();brief=daily_brief(db,now)
                self.assertEqual(brief['candidate_count'],8)
                self.assertEqual(brief['ready_count'],7)
                self.assertEqual(brief['pending_count'],1)
                self.assertEqual([p['score'] for p in brief['picks']],[56,55,54,53,52])
                self.assertEqual(brief['pending'][0]['reason'],'分析引用待核验')
        finally:engine.dispose()

    def test_empty_database_does_not_fabricate_recommendations(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:self.assertEqual(daily_brief(db)['picks'],[])
        finally:engine.dispose()
