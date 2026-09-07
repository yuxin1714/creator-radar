import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from sqlalchemy import select
from app.db import SessionLocal
from app.models.work import PlaybookRevision, PlaybookSource, utcnow
from app.providers.base import ProviderError

MAX_BYTES = 200_000
BUNDLE_VERSION = ".b2"


def git(*args, cwd=None):
    return subprocess.check_output(["git", *args], cwd=cwd, timeout=45, stderr=subprocess.PIPE)


def read_bundle(directory, skill_path):
    path = PurePosixPath(skill_path)
    if path.is_absolute() or ".." in path.parts or "\\" in skill_path or path.name != "SKILL.md":
        raise ProviderError("invalid_playbook", "Skill 路径无效。")
    # Read committed blobs, never follow checkout symlinks or execute repository code.
    entries = {}
    for entry in git("ls-tree", "-rz", "HEAD", cwd=directory).split(b"\0"):
        if not entry:
            continue
        metadata, filename = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        entries[filename.decode("utf-8")] = (mode, kind, blob)
    reference_prefix = str(path.parent / "references") + "/"
    files = [str(path)] + sorted(name for name in entries if name.startswith(reference_prefix) and name.endswith(".md"))
    if len(files) > 40:
        raise ProviderError("invalid_playbook", "Skill 引用文件过多。")
    documents, total = {}, 0
    for filename in files:
        entry = entries.get(filename)
        if not entry or entry[0] not in ("100644", "100755") or entry[1] != "blob":
            raise ProviderError("invalid_playbook", "Skill 文件缺失或不是普通文档。")
        size = int(git("cat-file", "-s", entry[2], cwd=directory))
        total += size
        if total > MAX_BYTES:
            raise ProviderError("invalid_playbook", "Skill 及引用文档总大小超过限制。")
        documents[filename] = git("cat-file", "blob", entry[2], cwd=directory).decode("utf-8-sig")
    content = documents[str(path)]
    if not re.match(r"\A---\r?\n", content) or not re.search(r"^name:\s*\S+", content, re.M) or "# " not in content:
        raise ProviderError("invalid_playbook", "SKILL.md 格式无效。")
    for document in documents.values():
        for reference in re.findall(r"references/[A-Za-z0-9_./-]+\.md", document):
            if str(path.parent / reference) not in documents:
                raise ProviderError("invalid_playbook", "Skill 中的引用文档缺失。")
    return content + "".join("\n\n---\n参考文档：" + filename + "\n\n" + text for filename, text in documents.items() if filename != str(path))


def sync_playbook(source_id: str):
    with SessionLocal() as db:
        source = db.get(PlaybookSource, source_id)
        if not source or source.source_type != "remote" or not source.repository_url or not source.skill_path:
            raise ProviderError("playbook_not_found", "远程 Playbook 不存在。")
        url, path = source.repository_url, source.skill_path
    if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", url):
        raise ProviderError("invalid_playbook", "仅支持 GitHub HTTPS 仓库。")
    try:
        scratch = Path(__file__).resolve().parents[4] / "work" / "playbook-sync"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sync-", dir=scratch) as directory:
            subprocess.run(["git", "clone", "--no-checkout", "--depth", "1", url, directory],
                           check=True, capture_output=True, timeout=45)
            # SHA is derived from the same clone used to read all content.
            commit = git("rev-parse", "HEAD", cwd=directory).decode().strip()
            content = read_bundle(directory, path)
        revision = commit + BUNDLE_VERSION
        with SessionLocal() as db:
            source = db.scalar(select(PlaybookSource).where(PlaybookSource.id == source_id).with_for_update())
            if not source or source.repository_url != url or source.skill_path != path:
                raise ProviderError("playbook_sync_failed", "Skill 来源已变化，请重新同步。")
            existing = db.get(PlaybookRevision, f"{source_id}:{revision}")
            updated = source.revision != revision or existing is None
            if not existing:
                db.add(PlaybookRevision(id=f"{source_id}:{revision}", source_id=source_id, revision=revision, content=content))
            elif existing.content != content:
                raise ProviderError("playbook_sync_failed", "已有版本内容不一致，未覆盖历史记录。")
            source.revision, source.synced_at = revision, utcnow()
            db.commit()
        return {"updated": updated, "revision": revision, "commit": commit}
    except ProviderError:
        raise
    except Exception as error:
        raise ProviderError("playbook_sync_failed", "无法同步远程 Playbook，请检查网络和仓库访问权限。") from error
