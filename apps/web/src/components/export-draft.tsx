"use client";

import { useState } from "react";
import { Download, LoaderCircle } from "lucide-react";

export function ExportDraft({ title, body, workId }: { title: string; body: string; workId: string | null }) {
  const [format, setFormat] = useState("txt");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setBusy(true);
    setError("");
    // Capture editor values before awaiting the reference lookup.
    const snapshot = { title: title.trim() || "未命名创作", body, format, workId };
    try {
      let reference = "";
      if (snapshot.workId) {
        const response = await fetch(`/api/works/${encodeURIComponent(snapshot.workId)}`, {
          cache: "no-store", signal: AbortSignal.timeout(10000),
        });
        if (!response.ok) throw new Error("无法读取参考来源，请稍后重试导出。");
        const work = await response.json();
        if (typeof work.source_url !== "string") throw new Error("参考来源缺失。");
        reference = `\n\n参考来源：${work.source_url}`;
      }
      const heading = snapshot.format === "md" ? `# ${snapshot.title.replace(/[\r\n]+/g, " ")}` : snapshot.title;
      const content = `${heading}\n\n${snapshot.body}${reference}\n`;
      const blob = new Blob([content], { type: snapshot.format === "md" ? "text/markdown;charset=utf-8" : "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename = snapshot.title.replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").replace(/[. ]+$/g, "").slice(0, 80) || "draft";
      link.href = url;
      link.download = `creator-radar-${filename}.${snapshot.format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setError(error instanceof Error ? error.message : "导出失败，请重试。");
    } finally {
      setBusy(false);
    }
  }

  return <div className="draft-export">
    <select aria-label="导出格式" value={format} disabled={busy} onChange={event => setFormat(event.target.value)}>
      <option value="txt">TXT</option>
      <option value="md">Markdown</option>
    </select>
    <button type="button" className="button button-outline" aria-label="导出当前草稿" title="导出当前草稿（包含未保存修改）" disabled={busy || !body.trim()} onClick={download}>
      {busy ? <LoaderCircle className="spin" size={16} /> : <Download size={16} />}
    </button>
    {error && <p role="alert">{error}</p>}
  </div>;
}
