from sqlalchemy import select
from app.core.config import Settings
from app.db import SessionLocal
from app.models.work import Transcript, Work
from app.providers.base import ProviderError
from app.providers.tikhub import TikHubProvider
from app.services.local_asr import transcribe_file
from app.services.media_download import download_media

def transcript_json(item: Transcript):
    return {"id": item.id, "status": item.status, "kind": item.kind, "language": item.language,
            "provider": item.provider, "text": item.text, "segments": item.segments,
            "error_summary": item.error_summary, "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat()}

def transcript_state(work: Work, settings: Settings):
    with SessionLocal() as db:
        existing = db.scalar(select(Transcript).where(Transcript.owner_id == "local-user", Transcript.work_id == work.id, Transcript.kind == "SOURCE"))
        if existing: return {"availability": "READY" if existing.status == "COMPLETED" else existing.status, "transcript": transcript_json(existing), "action": None}
    if work.platform == "youtube":
        return {"availability": "PLATFORM_CAPTIONS", "transcript": None, "action": "FETCH_CAPTIONS",
                "message": "可检查 YouTube 已有字幕；检查和获取可能分别产生 TikHub 请求费用。"}
    if settings.asr_provider == "local_faster_whisper" and settings.asr_model_path:
        return {"availability": "ASR_AVAILABLE", "transcript": None, "action": "TRANSCRIBE",
                "message": "已配置本地 GPU 转写。开始后会获取媒体文件，并在本机生成逐字稿。"}
    return {"availability": "ASR_REQUIRED", "transcript": None, "action": None,
            "message": "该平台没有通用字幕接口，需要先选择并配置 ASR 服务。"}

def prepare_transcript(work: Work, settings: Settings):
    if settings.asr_provider != "local_faster_whisper": raise ProviderError("asr_not_configured", "本地 ASR 尚未配置。")
    with SessionLocal() as db:
        item = db.scalar(select(Transcript).where(Transcript.owner_id == "local-user", Transcript.work_id == work.id, Transcript.kind == "SOURCE"))
        if item and item.status in ("PENDING", "PROCESSING", "COMPLETED"): return item
        item = item or Transcript(work_id=work.id, provider="faster-whisper", status="PENDING")
        item.status, item.error_summary = "PENDING", None
        db.add(item); db.commit(); return item

def process_transcript(work_id: str, settings: Settings | None = None):
    settings, media_path = settings or Settings(), None
    with SessionLocal() as db:
        work = db.scalar(select(Work).where(Work.id == work_id, Work.owner_id == "local-user"))
        item = db.scalar(select(Transcript).where(Transcript.owner_id == "local-user", Transcript.work_id == work_id, Transcript.kind == "SOURCE"))
        if not work or not item: return
        item.status = "PROCESSING"; db.commit()
        platform, external_id = work.platform, work.external_id
    try:
        media_url = TikHubProvider(settings.tikhub_api_key, settings.tikhub_base_url).fetch_media_url(platform, external_id)
        media_path = download_media(media_url, settings.media_cache_dir, settings.media_max_bytes)
        result = transcribe_file(media_path, settings.asr_model_path, settings.asr_device, settings.asr_compute_type)
        with SessionLocal() as db:
            item = db.scalar(select(Transcript).where(Transcript.work_id == work_id, Transcript.owner_id == "local-user", Transcript.kind == "SOURCE"))
            item.status, item.language = "COMPLETED", result["language"]
            item.provider, item.text, item.segments = "faster-whisper/large-v3-turbo", result["text"], result["segments"]
            item.error_summary = None; db.commit()
    except Exception as error:
        message = str(error) if isinstance(error, ProviderError) else "本地转写失败，请查看 API 日志。"
        with SessionLocal() as db:
            item = db.scalar(select(Transcript).where(Transcript.work_id == work_id, Transcript.owner_id == "local-user", Transcript.kind == "SOURCE"))
            if item: item.status, item.error_summary = "FAILED", message[:500]; db.commit()
    finally:
        if media_path: media_path.unlink(missing_ok=True)
