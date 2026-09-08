import asyncio
import json
import logging
import re
from datetime import timedelta
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, urlopen
from urllib.error import HTTPError, URLError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.models.creator import Creator, CreatorWork
from app.models.work import Work, WorkMetadata, utcnow
from app.providers.base import ProviderError
from app.providers.tikhub import normalize_payload
from app.services.link_resolution import SafeRedirect, _check_target, USER_AGENT


def creator_identity(text):
    urls = re.findall(r'https://[^\s<>]+', text)
    if len(urls) != 1:
        raise ProviderError('invalid_creator_link', '请填写一个抖音创作者主页链接。')
    url = urls[0].rstrip('。，,')
    parts = urlsplit(url)
    if parts.hostname not in ('www.douyin.com','douyin.com','v.douyin.com','www.iesdouyin.com'):
        raise ProviderError('invalid_creator_link', '当前创作者监控仅支持抖音主页。')
    _check_target(url)
    if parts.hostname == 'v.douyin.com':
        with build_opener(SafeRedirect()).open(Request(url, headers={'User-Agent':USER_AGENT}), timeout=15) as response:
            url = response.geturl()
        _check_target(url)
    match = re.fullmatch(r'/(?:share/)?user/(MS4w[A-Za-z0-9_-]{10,140})/?', urlsplit(url).path)
    if not match:
        raise ProviderError('invalid_creator_link', '链接不是创作者主页，请复制抖音主页分享链接。')
    sid = match.group(1)
    return sid, 'https://www.douyin.com/user/'+sid


def provider_get(settings, endpoint, params):
    if not settings.tikhub_api_key:
        raise ProviderError('provider_not_configured', '请先配置 TikHub。')
    request = Request(settings.tikhub_base_url.rstrip('/')+'/api/v1/douyin/web/'+endpoint+'?'+urlencode(params), headers={'Authorization':'Bearer '+settings.tikhub_api_key,'Accept':'application/json','User-Agent':'CreatorRadar/0.4'})
    try:
        with urlopen(request,timeout=30) as response:
            payload=json.load(response)
    except HTTPError as error:
        reason = '上游作品数据暂不可用，请稍后重试或联系 TikHub 支持。' if error.code == 400 else '请检查 TikHub 套餐或余额。' if error.code == 402 else '请检查 TikHub 权限。' if error.code in (401,403) else '请稍后重试。'
        raise ProviderError('creator_provider_error', f'创作者数据接口返回 HTTP {error.code}，{reason}') from error
    except (URLError, TimeoutError, ValueError) as error:
        raise ProviderError('creator_provider_error', '无法读取创作者数据，请稍后重试。') from error
    data=payload.get('data')
    if payload.get('code') not in (0,200) or not isinstance(data,dict) or data.get('status_code',0) != 0:
        raise ProviderError('creator_provider_error','平台未返回可用的创作者数据。')
    return data


def add_creator(text, daily, settings):
    sid,url=creator_identity(text)
    with SessionLocal() as db:
        existing=db.scalar(select(Creator).where(Creator.owner_id=='local-user',Creator.platform=='douyin',Creator.external_id==sid))
        if existing:return existing.id,False
    profile=provider_get(settings,'handler_user_profile',{'sec_user_id':sid}).get('user',{})
    if profile.get('sec_uid') != sid or not profile.get('nickname'):
        raise ProviderError('creator_mismatch','主页身份未通过验证，请检查链接。')
    with SessionLocal() as db:
        item=Creator(external_id=sid,name=profile['nickname'],source_url=url,daily=daily)
        db.add(item)
        try:db.commit()
        except IntegrityError:
            db.rollback()
            item=db.scalar(select(Creator).where(Creator.owner_id=='local-user',Creator.platform=='douyin',Creator.external_id==sid))
            if not item:raise
            return item.id,False
        return item.id,True


def check_creator(creator_id, settings, scheduled=False):
    with SessionLocal() as db:
        query=select(Creator).where(Creator.id==creator_id,Creator.owner_id=='local-user')
        if scheduled:query=query.where(Creator.daily.is_(True),Creator.next_check_at<=utcnow())
        item=db.scalar(query.with_for_update())
        if not item or item.status=='PROCESSING':return
        first=item.last_checked_at is None
        sid=item.external_id
        item.status,item.error_summary='PROCESSING',None
        item.next_check_at=utcnow()+timedelta(days=1)
        db.commit()
    new_count=0; cursor='0'; partial=False
    try:
        for page in range(1 if first else 3):
            data=provider_get(settings,'fetch_user_post_videos',{'sec_user_id':sid,'max_cursor':cursor,'count':20})
            posts=data.get('aweme_list')
            if not isinstance(posts,list):raise ProviderError('invalid_posts','作品列表格式异常。')
            page_new=0
            with SessionLocal() as db:
                for post in posts:
                    external=str(post.get('aweme_id',''))
                    if not external.isdigit() or post.get('author',{}).get('sec_uid') != sid:
                        raise ProviderError('invalid_posts','作品身份校验失败，已停止导入。')
                    work=db.scalar(select(Work).where(Work.owner_id=='local-user',Work.platform=='douyin',Work.external_id==external))
                    if not work:
                        work=Work(platform='douyin',external_id=external,source_url='https://www.douyin.com/video/'+external,status='READY')
                        # Handle a simultaneous manual import without duplicating the asset.
                        try:
                            with db.begin_nested():db.add(work);db.flush()
                        except IntegrityError:
                            work=db.scalar(select(Work).where(Work.owner_id=='local-user',Work.platform=='douyin',Work.external_id==external))
                    if not db.get(CreatorWork,(creator_id,work.id)):
                        db.add(CreatorWork(creator_id=creator_id,work_id=work.id));page_new+=1
                    result=normalize_payload('douyin',{'data':{'aweme_detail':post}})
                    metadata=db.get(WorkMetadata,work.id) or WorkMetadata(work_id=work.id,provider='tikhub')
                    for field in ('title','author_id','author_name','cover_url','duration_seconds','published_at','metrics'):
                        setattr(metadata,field,getattr(result,field))
                    metadata.fetched_at=utcnow();db.add(metadata)
                    work.title,work.status=result.title,'READY'
                db.commit()
            new_count+=page_new
            if first or not data.get('has_more') or not posts or page_new==0:break
            next_cursor=str(data.get('max_cursor','0'))
            if next_cursor==cursor:partial=True;break
            cursor=next_cursor
            if page==2:partial=True
        with SessionLocal() as db:
            item=db.get(Creator,creator_id)
            item.status='COMPLETED';item.last_checked_at=utcnow();item.last_new_count=new_count
            item.error_summary='本次达到分页上限，可能还有未收录作品；可手动检查。' if partial else None
            db.commit()
    except Exception as error:
        with SessionLocal() as db:
            item=db.get(Creator,creator_id)
            item.status='FAILED';item.last_new_count=new_count
            item.error_summary=str(error)[:500] if isinstance(error,ProviderError) else '检查更新失败，请稍后重试。'
            db.commit()


def check_due(settings):
    with SessionLocal() as db:
        ids=list(db.scalars(select(Creator.id).where(Creator.owner_id=='local-user',Creator.daily.is_(True),Creator.next_check_at<=utcnow(),Creator.status!='PROCESSING')))
    for creator_id in ids:check_creator(creator_id,settings,scheduled=True)


async def monitor_loop(settings):
    while True:
        try:
            check = asyncio.create_task(asyncio.to_thread(check_due,settings))
            try:await asyncio.shield(check)
            except asyncio.CancelledError:
                # Keep the process ownership lock until an in-flight check has ended.
                await check
                raise
        except Exception:logging.getLogger(__name__).warning('Creator monitor check failed; will retry on next tick')
        await asyncio.sleep(60)
