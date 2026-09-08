from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from app.models.work import Work
from app.models.work_preferences import WorkPreferences
from app.providers.base import ProviderError


class PreferencesInput(BaseModel):
    favorite: bool
    archived: bool
    tags: list[str] = Field(max_length=12)
    expected_revision: int = Field(ge=0)

    @field_validator('tags')
    @classmethod
    def clean_tags(cls, values):
        tags=list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if any(len(tag)>30 for tag in tags):raise ValueError('每个标签最多 30 字符')
        return tags


def preferences_json(item):
    return {'favorite':item.favorite,'archived':item.archived,'tags':item.tags,'revision':item.revision} if item else {'favorite':False,'archived':False,'tags':[],'revision':0}


def save_preferences(db,work_id,body):
    work=db.scalar(select(Work).where(Work.id==work_id,Work.owner_id=='local-user').with_for_update())
    if not work:raise ProviderError('work_not_found','作品不存在。')
    item=db.get(WorkPreferences,work_id)
    if (item.revision if item else 0)!=body.expected_revision:
        raise ProviderError('preference_conflict','作品标签或收藏已在其他页面更新，请刷新后重试。')
    item=item or WorkPreferences(work_id=work_id,revision=0)
    item.favorite,item.archived,item.tags=body.favorite,body.archived,body.tags
    item.revision+=1;db.add(item);db.commit()
    return preferences_json(item)
