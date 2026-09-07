"use client";
import { useRef, useState } from "react";
import { Pencil, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";

export function EditPlaybook({ id, onSaved }: { id: string; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [rules, setRules] = useState("");
  const [revision, setRevision] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function open() {
    dialog.current?.showModal(); setBusy(true); setError(""); setRevision("");
    try {
      const response = await fetch(`/api/playbooks/${encodeURIComponent(id)}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "读取失败");
      setName(data.name); setDescription(data.description || ""); setRules(data.rules.join("\n")); setRevision(data.revision);
    } catch (e) { setError(e instanceof Error ? e.message : "读取失败"); }
    finally { setBusy(false); }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await fetch(`/api/playbooks/${encodeURIComponent(id)}`, {
        method: "PATCH", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: name.trim(), description, rules: rules.split("\n").map(x => x.trim()).filter(Boolean), expected_revision: revision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "保存失败，请检查名称和规则长度。");
      dialog.current?.close(); onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : "保存失败"); }
    finally { setBusy(false); }
  }
  return <>
    <Button variant="outline" onClick={open}><Pencil size={15} />编辑</Button>
    <dialog ref={dialog} className="add-dialog" aria-label="编辑自定义 Skill">
      <div className="dialog-top"><h2>编辑自定义 Skill</h2><button type="button" className="button button-ghost" aria-label="关闭编辑" title="关闭编辑" onClick={() => dialog.current?.close()}><X size={18} /></button></div>
      {busy && !revision ? <p role="status">正在读取…</p> : null}
      {error && <p role="alert">{error}</p>}
      {revision && <form onSubmit={save} className="creation-form">
        <label>Skill 名称<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>说明<input maxLength={1000} value={description} onChange={e => setDescription(e.target.value)} /></label>
        <label>规则<textarea aria-label="规则" value={rules} onChange={e => setRules(e.target.value)} /></label>
        <p>当前版本 {revision}</p>
        <Button disabled={busy || !name.trim()} type="submit"><Save size={15} />保存 Skill</Button>
      </form>}
    </dialog>
  </>;
}
