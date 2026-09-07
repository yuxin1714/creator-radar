"use client";

import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export type DraftSnapshot = {
  title: string; idea: string | null; body: string | null; output_language: string;
  brief: { platform: string; content_type: string; direction: string; style: string; playbook_id: string } | null;
};
type Version = { id: string; version_number: number; snapshot: DraftSnapshot; created_at: string };

export function DraftHistory({ projectId, refresh, onLoad }: { projectId: string; refresh: number; onLoad: (snapshot: DraftSnapshot) => void }) {
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setError("");
    fetch(`/api/creation-projects/${encodeURIComponent(projectId)}/versions`, { cache: "no-store", signal: controller.signal })
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "读取失败");
        if (!controller.signal.aborted) { setVersions(data); setSelected(data[0]?.id || ""); }
      })
      .catch(error => { if (!controller.signal.aborted) setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId, open, refresh]);
  const version = versions.find(version => version.id === selected);
  return <details className="draft-history" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>版本历史</summary>
    {loading ? <p role="status">正在读取版本…</p> : error ? <p role="alert">{error}</p> : <>
      {versions.length === 0 ? <p>暂无保存版本。</p> : <>
        <label>最近 50 个版本<select value={selected} onChange={event => setSelected(event.target.value)}>
          {versions.map(version => <option key={version.id} value={version.id}>V{version.version_number} · {new Date(version.created_at).toLocaleString("zh-CN")}</option>)}
        </select></label>
        {version && <div className="history-preview"><h3>{version.snapshot.title}</h3><p>{version.snapshot.idea}</p><pre>{version.snapshot.body || "（正文为空）"}</pre>
          <Button variant="outline" onClick={() => onLoad(version.snapshot)}><RotateCcw size={15} />载入此版本</Button>
        </div>}
      </>}
    </>}
  </details>;
}
