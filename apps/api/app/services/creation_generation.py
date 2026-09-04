import json
import urllib.request
from app.core.config import Settings
from app.db import SessionLocal
from app.models.work import CreationBrief, CreationGeneration, CreationProject, PlaybookRevision, PlaybookSource
from app.providers.base import ProviderError

def generate(project_id: str, generation_id: str, settings: Settings | None = None):
    settings = settings or Settings()
    with SessionLocal() as db:
        project = db.get(CreationProject, project_id); brief = db.get(CreationBrief, project_id); item = db.get(CreationGeneration, generation_id)
        if not project or not brief or not item: raise ProviderError("project_not_found", "创作项目不存在。")
        source = db.get(PlaybookSource, brief.playbook_id); revision = source.revision if source else None
        saved = db.get(PlaybookRevision, f"{brief.playbook_id}:{revision}") if revision else None
        skill = saved.content if saved else "默认规则：使用独立观点和事实，避免逐句复刻参考内容。"
        item.status, item.playbook_revision = "PROCESSING", revision; db.commit()
        context = {"platform": brief.platform, "content_type": brief.content_type, "direction": brief.direction, "style": brief.style, "title": project.title, "idea": project.idea or "", "existing_draft": project.body or "", "skill": skill}
    prompt = "你是内容创作编辑。根据以下项目配置生成一份可直接发布的草稿。必须遵循 Skill 规则；若事实未验证，用【待核验】标记。不要解释过程，不要使用 Markdown 标题，不要模仿或复述任何未提供的参考作品。按目标平台给出自然、原生的正文。\n\n" + json.dumps(context, ensure_ascii=False)
    payload = json.dumps({"model": settings.llm_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}).encode()
    request = urllib.request.Request(settings.llm_base_url.rstrip("/") + "/v1/chat/completions", data=payload, headers={"Authorization": "Bearer " + settings.llm_api_key, "Content-Type": "application/json"})
    try:
        response = json.load(urllib.request.urlopen(request, timeout=120)); content = response["choices"][0]["message"]["content"]
        with SessionLocal() as db:
            item = db.get(CreationGeneration, generation_id); item.status, item.content, item.error_summary = "COMPLETED", content, None; db.commit()
    except Exception:
        with SessionLocal() as db:
            item = db.get(CreationGeneration, generation_id)
            if item: item.status, item.error_summary = "FAILED", "生成失败，请检查 API 日志或重试。"; db.commit()
