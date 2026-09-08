import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models.work import PlaybookSource,PlaybookRevision,CreationProject,CreationBrief,GenerationInput
from app.services.playbook_matching import PlaybookRouting,MatchingInput,recommend_playbooks
from app.services.generation_workflow import prepare_generation,GenerationOptions
from app.core.config import Settings


class PlaybookMatchingTests(unittest.TestCase):
    def test_matching_excludes_unavailable_and_freezes_actual_skill(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                db.add(PlaybookSource(id='story',name='Story Skill',source_type='custom',revision='1.0'));db.flush()
                db.add_all([PlaybookRevision(id='story:1.0',source_id='story',revision='1.0',content='Use a story'),PlaybookRouting(source_id='story',criteria=MatchingInput(content_types=['story'],styles=['storytelling']).model_dump())])
                project=CreationProject(title='Auto');db.add(project);db.flush();db.add(CreationBrief(project_id=project.id,playbook_id='auto',content_type='story',style='storytelling'));db.commit()
                matches=recommend_playbooks(db,'tiktok','story','cross_domain','storytelling')
                self.assertEqual(matches[0]['id'],'story')
                self.assertEqual(recommend_playbooks(db,'tiktok','tutorial','cross_domain','storytelling')[0]['id'],'structure-borrowing-v1')
                gen=prepare_generation(db,project.id,GenerationOptions(),Settings(llm_model='test'))
                self.assertEqual(gen.playbook_id,'story')
                self.assertEqual(db.get(GenerationInput,gen.id).context['skill'],'Use a story')
                db.get(PlaybookSource,'story').status='DISABLED';db.flush()
                self.assertEqual(recommend_playbooks(db,'tiktok','story','cross_domain','storytelling')[0]['id'],'structure-borrowing-v1')
        finally:engine.dispose()
