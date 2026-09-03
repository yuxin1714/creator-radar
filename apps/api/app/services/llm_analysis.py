import json
import urllib.request
from app.core.config import Settings
from app.db import SessionLocal
from app.models.work import Analysis, Transcript
from app.providers.base import ProviderError

def configured(settings: Settings) -> bool:
    return bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)

def process_analysis(work_id: str, settings: Settings | None = None):
    settings = settings or Settings()
    with SessionLocal() as db:
        item = db.query(Analysis).filter_by(work_id=work_id, owner_id="local-user").first()
        transcript = db.query(Transcript).filter_by(work_id=work_id, owner_id="local-user", kind="SOURCE").first()
        if not item or not transcript or transcript.status != "COMPLETED" or not transcript.text:
            raise ProviderError("transcript_required", "请先完成原文逐字稿。")
        item.status, item.error_summary = "PROCESSING", None; db.commit()
        text = transcript.text
    prompt = """你是短视频内容分析师。只根据给定逐字稿输出中文 JSON，不要使用 Markdown。字段必须为：summary（字符串）、hook（字符串）、structure（字符串数组）、key_points（字符串数组）、content_score（0到100整数）、score_reasons（字符串数组）、evidence（对象数组，每项含 claim 和 quote）。quote 必须是逐字稿中的原文短句。若无法确定，明确说明，不要编造。\n\n逐字稿：\n""" + text
    payload = json.dumps({"model": settings.llm_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "response_format": {"type": "json_object"}}).encode()
    request = urllib.request.Request(settings.llm_base_url.rstrip("/") + "/v1/chat/completions", data=payload, headers={"Authorization": "Bearer " + settings.llm_api_key, "Content-Type": "application/json"})
    try:
        response = json.load(urllib.request.urlopen(request, timeout=120))
        content = response["choices"][0]["message"]["content"]
        result = json.loads(content)
        if not isinstance(result, dict): raise ValueError("结果不是对象")
        with SessionLocal() as db:
            item = db.query(Analysis).filter_by(work_id=work_id, owner_id="local-user").first()
            item.status, item.result, item.error_summary = "COMPLETED", result, None; db.commit()
    except Exception:
        with SessionLocal() as db:
            item = db.query(Analysis).filter_by(work_id=work_id, owner_id="local-user").first()
            if item: item.status, item.error_summary = "FAILED", "模型分析失败，请检查 API 日志或重试。"; db.commit()
