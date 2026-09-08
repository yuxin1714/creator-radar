import unittest
from unittest.mock import patch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.core.config import Settings
from app.models.creator import Creator, CreatorWork
from app.models.work import Work
from app.services import creator_monitor as monitor
from app.providers.base import ProviderError
from app import creator_routes


class CreatorMonitorTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://');Base.metadata.create_all(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        self.override=patch.object(monitor,'SessionLocal',self.sessions);self.override.start()
        self.sid='MS4wLjABAAAAabcdefghij'
        with self.sessions() as db:
            item=Creator(name='Test creator',external_id=self.sid,source_url='https://www.douyin.com/user/'+self.sid)
            db.add(item);db.commit();self.cid=item.id
        self.posts={'aweme_list':[{'aweme_id':'123456789','desc':'Test post','author':{'sec_uid':self.sid,'uid':'123','nickname':'Test creator'},'video':{'duration':15000},'statistics':{}}],'has_more':0}

    def tearDown(self):self.override.stop();self.engine.dispose()

    def test_daily_check_deduplicates_and_keeps_metadata(self):
        with patch.object(monitor,'provider_get',return_value=self.posts) as provider:
            monitor.check_creator(self.cid,Settings())
            monitor.check_due(Settings())
            self.assertEqual(provider.call_count,1)
            monitor.check_creator(self.cid,Settings())
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(Work)).all()),1)
            self.assertEqual(len(db.scalars(select(CreatorWork)).all()),1)
            item=db.get(Creator,self.cid)
            self.assertEqual(item.last_new_count,0)
            self.assertEqual(item.status,'COMPLETED')

    def test_foreign_author_cannot_enter_feed(self):
        self.posts['aweme_list'][0]['author']['sec_uid']='other'
        with patch.object(monitor,'provider_get',return_value=self.posts):monitor.check_creator(self.cid,Settings())
        with self.sessions() as db:
            self.assertEqual(db.get(Creator,self.cid).status,'FAILED')
            self.assertEqual(len(db.scalars(select(Work)).all()),0)

    def test_paused_daily_check_makes_no_request(self):
        with self.sessions() as db:db.get(Creator,self.cid).daily=False;db.commit()
        with patch.object(monitor,'provider_get') as provider:
            monitor.check_due(Settings());provider.assert_not_called()

    def test_feed_ownership_and_daily_setting(self):
        with patch.object(monitor,'provider_get',return_value=self.posts):monitor.check_creator(self.cid,Settings())
        with patch.object(creator_routes,'SessionLocal',self.sessions):
            items=creator_routes.list_feed(self.cid)
            self.assertEqual(len(items),1)
            self.assertEqual(items[0]['title'],'Test post')
            self.assertEqual(creator_routes.get_creator(self.cid)['stats'],{'works':1,'transcripts':0,'analyses':0})
            self.assertFalse(creator_routes.update_creator(self.cid,creator_routes.CreatorPreference(daily=False))['daily'])
            with self.sessions() as db:
                db.get(Creator,self.cid).owner_id='other';db.commit()
            self.assertEqual(creator_routes.list_feed(self.cid),[])
            self.assertEqual(creator_routes.list_creators(),[])
            self.assertEqual(creator_routes.get_creator(self.cid).status_code,404)
            self.assertEqual(creator_routes.update_creator(self.cid,creator_routes.CreatorPreference(daily=True)).status_code,404)

    def test_rejects_non_homepage_and_sanitizes_share_parameters(self):
        with patch.object(monitor,'_check_target'):
            sid,url=monitor.creator_identity('https://www.iesdouyin.com/share/user/'+self.sid+'?tracking=private')
            self.assertEqual(sid,self.sid);self.assertNotIn('tracking',url)
            with self.assertRaises(ProviderError):monitor.creator_identity('https://www.douyin.com/video/123')
        with self.assertRaises(ProviderError):monitor.creator_identity('https://localhost/user/'+self.sid)
