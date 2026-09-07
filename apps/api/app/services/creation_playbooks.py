import json

from app.models.work import PlaybookRevision, PlaybookSource
from app.providers.base import ProviderError

PLAYBOOKS = {
    "structure-borrowing-v1": {
        "name": "结构借鉴，观点重构",
        "version": "1.0",
        "rules": ["只借鉴叙事结构和注意力机制，不逐句改写原文。", "使用独立观点、论据和案例。", "事实、数据和具体结论必须标记待核验。", "按目标平台重新组织输出，而非跨平台搬运。"],
    }
}

def resolve_playbook(db, playbook_id: str, revision: str | None = None) -> tuple[str, str]:
    source = db.get(PlaybookSource, playbook_id)
    if source:
        if source.status != "ACTIVE":
            raise ProviderError("playbook_disabled", "所选 Skill 已停用，请重新选择。")
        saved = db.get(PlaybookRevision, f"{playbook_id}:{revision or source.revision}")
        if not saved or not saved.content.strip():
            raise ProviderError("playbook_not_synced", "所选 Skill 尚无可用内容，请先在设置中同步。")
        return saved.revision, saved.content
    builtin = PLAYBOOKS.get(playbook_id)
    if builtin:
        if revision and revision != builtin["version"]:
            raise ProviderError("playbook_version_missing", "所选内置 Skill 版本不可用。")
        return builtin["version"], json.dumps(builtin, ensure_ascii=False)
    raise ProviderError("playbook_not_found", "所选 Skill 不存在，请重新选择。")
