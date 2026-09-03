import subprocess
import tempfile
from pathlib import Path
from app.db import SessionLocal
from app.models.work import PlaybookRevision, PlaybookSource
from app.providers.base import ProviderError

def sync_playbook(source_id: str):
    with SessionLocal() as db:
        source = db.get(PlaybookSource, source_id)
        if not source or not source.repository_url or not source.skill_path: raise ProviderError("playbook_not_found", "远程 Playbook 不存在。")
        url, path = source.repository_url, source.skill_path
    try:
        revision = subprocess.check_output(["git", "ls-remote", url, "HEAD"], text=True, timeout=20).split()[0]
        with SessionLocal() as db:
            source = db.get(PlaybookSource, source_id)
            existing = db.get(PlaybookRevision, f"{source_id}:{revision}")
            if existing: return {"updated": False, "revision": revision}
        with tempfile.TemporaryDirectory(prefix="creator-radar-playbook-") as directory:
            subprocess.run(["git", "clone", "--depth", "1", url, directory], check=True, capture_output=True, text=True, timeout=45)
            content = (Path(directory) / path).read_text(encoding="utf-8")
        if not content.startswith("---") or "# " not in content or len(content) > 200_000: raise ProviderError("invalid_playbook", "SKILL.md 格式或大小无效。")
        with SessionLocal() as db:
            source = db.get(PlaybookSource, source_id); source.revision = revision
            db.add(PlaybookRevision(id=f"{source_id}:{revision}", source_id=source_id, revision=revision, content=content)); db.commit()
        return {"updated": True, "revision": revision}
    except ProviderError: raise
    except Exception as error: raise ProviderError("playbook_sync_failed", "无法同步远程 Playbook。") from error
