import unittest
from unittest.mock import patch
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.core.config import Settings
from app.models.work import Work,Transcript,Analysis
from app.models.research import ResearchRun
from app.services import research
from app import research_routes
from app.providers.base import ProviderError


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        self.worker_patch=patch.object(research,'SessionLocal',self.sessions);self.worker_patch.start()
        self.route_patch=patch.object(research_routes,'SessionLocal',self.sessions);self.route_patch.start()
        self.settings=Settings(llm_api_key='test',llm_base_url='https://example.test',llm_model='test')
        with self.sessions() as db:
            work=Work(platform='douyin',external_id='test',source_url='https://example.test');db.add(work);db.flush();self.wid=work.id
            db.add(Transcript(work_id=work.id,status='COMPLETED',text='真实原文',language='zh'));db.commit()

    def tearDown(self):self.worker_patch.stop();self.route_patch.stop();self.engine.dispose()

    def start(self,kind='translation',language='en'):
        with self.sessions() as db:
            item=research.prepare_research(db,self.wid,research.ResearchInput(kind=kind,language=language),self.settings);db.commit();return item.id

    def test_translation_uses_snapshot_and_never_overwrites_source(self):
        rid=self.start()
        with self.sessions() as db:
            with self.assertRaises(ProviderError):research.prepare_research(db,self.wid,research.ResearchInput(kind='analysis',language='zh-CN'),self.settings)
            db.scalar(select(Transcript).where(Transcript.work_id==self.wid)).text='修改后的原文';db.commit()
        with patch.object(research,'request_json',return_value={'translation':'Original source'}) as model:
            research.process_research(rid,self.settings);research.process_research(rid,self.settings)
            self.assertEqual(model.call_count,1);self.assertEqual(model.call_args.args[3],'真实原文')
        data=research_routes.get_research(self.wid,'translation','en')
        self.assertTrue(data['history'][0]['source_stale']);self.assertEqual(data['history'][0]['result']['translation'],'Original source')
        with self.sessions() as db:self.assertEqual(db.scalar(select(Transcript).where(Transcript.work_id==self.wid)).text,'修改后的原文')

    def test_analysis_retains_old_language_and_requires_original_quotes(self):
        legacy={'summary':'中文旧报告'}
        with self.sessions() as db:db.add(Analysis(work_id=self.wid,status='COMPLETED',analysis_language='zh-CN',result=legacy));db.commit()
        rid=self.start('analysis','en')
        result={'summary':'Summary','hook':'Hook','structure':['Structure'],'key_points':['Point'],'content_score':70,'score_reasons':['Reason'],'evidence':[{'claim':'Claim','quote':'真实原文'}]}
        with patch.object(research,'request_json',return_value=result) as model:
            research.process_research(rid,self.settings);self.assertIn('English',model.call_args.args[2])
        old=research_routes.get_research(self.wid,'analysis','zh-CN')['history'][0]
        new=research_routes.get_research(self.wid,'analysis','en')['history'][0]
        self.assertEqual(old['result'],legacy);self.assertEqual(new['result'],result);self.assertTrue(new['evidence_verified'])
        failed=self.start('analysis','en')
        result['evidence'][0]['quote']='Not in source'
        with patch.object(research,'request_json',return_value=result):research.process_research(failed,self.settings)
        with self.sessions() as db:
            self.assertEqual(db.get(ResearchRun,failed).status,'FAILED')
            self.assertEqual(db.get(ResearchRun,rid).status,'COMPLETED')

    def test_foreign_work_is_hidden_and_chunking_preserves_source(self):
        with self.sessions() as db:db.get(Work,self.wid).owner_id='other';db.commit()
        self.assertEqual(research_routes.get_research(self.wid,'translation','en').status_code,404)
        source=('Sentence. '*1600)+'结尾'
        parts=research.chunks(source)
        self.assertEqual(''.join(parts),source);self.assertTrue(all(len(part)<=6000 for part in parts))
