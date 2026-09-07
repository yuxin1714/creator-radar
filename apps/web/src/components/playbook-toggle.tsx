"use client";
import { useState } from "react";

export function PlaybookToggle({ id, name, enabled, onChanged }: { id: string; name: string; enabled: boolean; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function change(value: boolean) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/playbooks/${encodeURIComponent(id)}/status`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ enabled: value }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "更新失败");
      onChanged();
    } catch (error) { setError(error instanceof Error ? error.message : "更新失败"); }
    finally { setBusy(false); }
  }
  return <div><label><input type="checkbox" role="switch" aria-label={`启用 ${name}`} checked={enabled} disabled={busy} onChange={event => change(event.target.checked)} />{enabled ? "已启用" : "已停用"}</label>{error && <p role="alert">{error}</p>}</div>;
}
