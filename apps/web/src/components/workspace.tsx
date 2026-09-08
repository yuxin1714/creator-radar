"use client";

import Link from "next/link";
import { LocalSettings } from "@/components/local-settings";
import { CreatorImport } from "@/components/creator-import";
import { CreationSpace } from "@/components/creation-space";
import { DailyBrief } from "@/components/daily-brief";
import { PlaybookRouting } from "@/components/playbook-matching";
import { RegisterPlaybook } from "@/components/register-playbook";
import { WorkLibrary } from "@/components/work-library";
import { CreatorMonitor, CreatorFeed } from "@/components/creator-monitor";
import { TaskCenter } from "@/components/task-center";
import { PlaybookToggle } from "@/components/playbook-toggle";
import { EditPlaybook } from "@/components/edit-playbook";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { ArrowRight, ArrowUpRight, Check, CheckCircle2, CircleDot, Compass, FileText, FolderOpen, Globe2, Link2, LoaderCircle, Menu, Plus, Radar, Rss, Settings2, ShieldCheck, Sparkles, Users, Workflow, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { sections } from "@/lib/navigation";

type Result = { platform: "douyin" | "tiktok" | "youtube"; status: "recognized" | "needs_resolution"; external_id: string | null; normalized_url: string | null; message: string; imported: false; availability_checked: boolean; resolved_from_short_link?: boolean };
const platformNames = { douyin: "抖音", tiktok: "TikTok", youtube: "YouTube" };
const icons = [Radar, Rss, Users, FolderOpen, FileText, Workflow, Settings2];
const AddContext = createContext<() => void>(() => {});

function AddDialog({ dialogRef }: { dialogRef: React.RefObject<HTMLDialogElement | null> }) {
  const [mode,setMode]=useState<"work"|"creator">("work");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [imported, setImported] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const generation = useRef(0);
  function resetRequest() {
    generation.current += 1;
    abortRef.current?.abort();
    setBusy(false);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || busy) return;
    if (/https:\/\/(?:www\.)?(?:iesdouyin|douyin)\.com\/(?:share\/)?user\//i.test(text)) { setMode("creator"); return; }
    const run = ++generation.current;
    abortRef.current = new AbortController();
    setBusy(true); setError(""); setImported(""); setResult(null);
    try {
      const response = await fetch("/api/links/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }), signal: abortRef.current.signal });
      const data = await response.json();
      if (run !== generation.current) return;
      if (!response.ok) { setError(data.message ?? "验证失败，请稍后重试。"); return; }
      setResult(data);
    } catch {
      if (run === generation.current) setError("网络连接中断，请重试。");
    } finally { if (run === generation.current) setBusy(false); }
  }
  async function importWork() {
    if (!result?.normalized_url || !result.external_id || !result.availability_checked || busy) return;
    setBusy(true); setError(""); setImported("");
    try {
      const response = await fetch("/api/imports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform: result.platform, external_id: result.external_id, normalized_url: result.normalized_url, availability_checked: result.availability_checked }) });
      const data = await response.json();
      if (!response.ok) { setError(data.message ?? "导入失败，请重试。"); return; }
      setImported(data.message); window.dispatchEvent(new Event("creator-radar:refresh"));
    } catch { setError("网络连接中断，未能导入作品。"); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialogRef} className="add-dialog" aria-labelledby="add-title" onCancel={resetRequest} onClose={resetRequest}>
    <div className="dialog-top"><div className="icon-box"><Link2 size={22} /></div><Button variant="ghost" aria-label="关闭添加窗口" onClick={() => dialogRef.current?.close()}><X size={20} /></Button></div>
    <p className="eyebrow">ADD TO YOUR RADAR</p><h2 id="add-title">{mode==="work"?"添加参考作品":"添加对标创作者"}</h2><div className="add-kind"><Button variant={mode==="work"?"default":"outline"} onClick={()=>{resetRequest();setMode("work")}}>作品链接</Button><Button variant={mode==="creator"?"default":"outline"} onClick={()=>{resetRequest();setMode("creator")}}>创作者主页</Button></div>
    {mode==="creator"?<CreatorImport initialText={text}/>:<><p className="dialog-description">粘贴作品地址或分享文字，先确认平台与作品标识。</p>
    <form onSubmit={submit}>
      <label htmlFor="work-link">作品链接</label>
      <textarea autoFocus id="work-link" placeholder="粘贴抖音、TikTok 或 YouTube 作品链接…" value={text} maxLength={4000} disabled={busy} onChange={event => { setText(event.target.value); setResult(null); setError(""); setImported(""); }} rows={4} aria-describedby="link-help" />
      <div className="input-footer"><span id="link-help">一次一条 · 支持分享文字</span><span>{text.length} / 4000</span></div>
      <div className="platforms"><span>抖音</span><span>TikTok</span><span>YouTube</span></div>
      <div aria-live="polite">
        {error && <div role="alert" className="result error"><strong>暂未通过验证</strong><p>{error}</p></div>}
        {result && <div className={"result " + (result.status === "recognized" ? "success" : "warning")}>
          <strong>{result.status === "recognized" ? <CheckCircle2 size={18} /> : <Link2 size={18} />}{result.status === "recognized" ? (result.resolved_from_short_link ? "短链接已安全展开" : "作品地址已确认") : "平台已识别，短链接待展开"}</strong>
          <dl><div><dt>平台</dt><dd>{platformNames[result.platform]}</dd></div>{result.external_id && <div><dt>作品 ID</dt><dd className="mono">{result.external_id}</dd></div>}</dl>
          {result.normalized_url && <div className="normalized"><span>规范化地址</span><code>{result.normalized_url}</code></div>}
          <p>{result.message}</p>{result.status === "recognized" && <><Button className="import-button" type="button" disabled={busy || !!imported} onClick={importWork}>{imported ? <Check size={16} /> : <Plus size={16} />}{imported ? "已在作品库中" : "确认导入作品库"}</Button>{imported && <p className="import-message">{imported}</p>}</>}
        </div>}
      </div>
      <div className="scope-note"><ShieldCheck size={17} /><span>验证会访问平台网页并安全跟随短链接；确认后才保存作品。不会下载媒体或产生第三方 API 费用。</span></div>
      <div className="dialog-actions"><Button variant="outline" type="button" onClick={() => dialogRef.current?.close()}>关闭</Button><Button type="submit" disabled={busy || !text.trim()}>{busy ? <LoaderCircle className="spin" size={16} /> : <Link2 size={16} />}{busy ? "正在处理…" : error ? "重新验证" : "验证作品链接"}</Button></div>
    </form></>}
  </dialog>;
}

export function Workspace({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const current = sections.find(section => pathname === "/" + section.slug || pathname.startsWith("/" + section.slug + "/"));
  const openAdd = () => dialogRef.current?.showModal();
  return <AddContext.Provider value={openAdd}>
    <div className="workspace">
      <aside className={"sidebar " + (menuOpen ? "menu-open" : "")} aria-label="工作台导航">
        <Link href="/today" className="brand" onClick={() => setMenuOpen(false)}><span className="brand-mark"><Radar size={25} /></span><span>Creator Radar<small>内容情报与创作工作台</small></span></Link>
        <div className="workspace-label"><span className="avatar">我</span><div>个人工作台<small>LOCAL WORKSPACE</small></div><span className="tiny-dot" /></div>
        <p className="nav-label">发现与研究</p>
        <nav>{sections.slice(0, 4).map((section, index) => { const Icon = icons[index]; return <Link key={section.slug} href={"/" + section.slug} aria-current={current?.slug === section.slug ? "page" : undefined} onClick={() => setMenuOpen(false)}><Icon size={18} />{section.title}{current?.slug === section.slug && <span className="active-dot" />}</Link>; })}</nav>
        <p className="nav-label">创作与管理</p>
        <nav>{sections.slice(4).map((section, index) => { const Icon = icons[index + 4]; return <Link key={section.slug} href={"/" + section.slug} aria-current={current?.slug === section.slug ? "page" : undefined} onClick={() => setMenuOpen(false)}><Icon size={18} />{section.title}{current?.slug === section.slug && <span className="active-dot" />}</Link>; })}</nav>
        <div className="sidebar-bottom"><div className="build-label"><span className="tiny-dot" /> V1 · 开发预览</div><p>从发现到表达<br />积累自己的创作判断。</p><div className="profile"><span className="avatar small">我</span><span>本机预览<small>账户功能尚未接入</small></span></div></div>
      </aside>
      {menuOpen && <button className="menu-scrim" aria-label="收起导航" onClick={() => setMenuOpen(false)} />}
      <div className="workspace-main">
        <header className="topbar"><div className="breadcrumb"><Button variant="ghost" className="menu-toggle" aria-label="展开导航" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}><Menu size={20} /></Button><span>工作台</span><span className="slash">/</span><strong>{current?.title ?? "Creator Radar"}</strong></div><div className="topbar-actions"><span className="local-tag"><span className="tiny-dot" />本地开发</span><Button onClick={openAdd}><Plus size={17} />添加</Button></div></header>
        <main id="main-content" className="page-content">{children}</main>
        <footer className="workspace-footer"><span>CREATOR RADAR</span><span>让灵感有迹可循</span></footer>
      </div>
    </div><AddDialog dialogRef={dialogRef} />
  </AddContext.Provider>;
}

function Empty({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{description}</p>{action}</div>;
}
function AddButton() {
  const add = useContext(AddContext);
  return <Button onClick={add}><Plus size={16} />添加作品链接</Button>;
}
function Heading({ section }: { section: string }) {
  const data = sections.find(item => item.slug === section)!;
  return <div className="page-heading"><div><p className="eyebrow">{section === "today" ? "YOUR DAILY CREATIVE BRIEF" : "YOUR CREATIVE WORKSPACE"}</p><h1>{data.title}</h1><p>{data.description}</p></div><span className="phase-tag">P0 · 本地工作台</span></div>;
}

type WorkItem = { id:string; platform:keyof typeof platformNames; external_id:string; source_url:string; title:string|null; status:string; metadata:{author_name:string|null}|null; created_at:string };
function useCollection<T>(url:string) {
  const [items,setItems]=useState<T[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState("");
  useEffect(()=>{ let active=true; const load=async()=>{setLoading(true);try{const r=await fetch(url,{cache:"no-store"});const d=await r.json();if(!r.ok)throw new Error(d.message);if(active){setItems(d);setError("");}}catch(e){if(active)setError(e instanceof Error?e.message:"读取失败");}finally{if(active)setLoading(false);}};load();window.addEventListener("creator-radar:refresh",load);return()=>{active=false;window.removeEventListener("creator-radar:refresh",load)};},[url]);
  return {items,loading,error};
}
function CustomPlaybookForm({onCreated}:{onCreated:()=>void}){const [name,setName]=useState(""),[description,setDescription]=useState(""),[rules,setRules]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState("");async function create(){if(!name.trim())return;setBusy(true);try{const r=await fetch("/api/playbooks",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({name,description,rules:rules.split("\n").map(x=>x.trim()).filter(Boolean)})});const d=await r.json();if(!r.ok)throw new Error(d.message);setName("");setDescription("");setRules("");setMessage("自定义 Skill 已添加。");onCreated()}catch(e){setMessage(e instanceof Error?e.message:"添加失败。")}finally{setBusy(false)}}return <section className="panel skill-create"><div className="section-heading"><div><h2>添加自定义 Skill</h2><p>把你的创作方法论保存为可复用 Playbook。</p></div></div><div className="creation-form"><input aria-label="Skill 名称" placeholder="名称" value={name} onChange={e=>setName(e.target.value)}/><input aria-label="Skill 描述" placeholder="适用场景或说明" value={description} onChange={e=>setDescription(e.target.value)}/><textarea aria-label="Skill 规则" placeholder="每行一条规则" value={rules} onChange={e=>setRules(e.target.value)}/><Button disabled={busy||!name.trim()} onClick={create}>{busy?<LoaderCircle className="spin" size={15}/>:<Plus size={15}/>}添加 Skill</Button>{message&&<p className="provider-message">{message}</p>}</div></section>}
function SettingsPanel(){const [skills,setSkills]=useState<Array<{id:string;name:string;status:string;source_type:string;repository_url:string|null;revision:string|null;synced_at:string}>>([]),[message,setMessage]=useState(""),[syncing,setSyncing]=useState("");const load=()=>fetch("/api/playbooks?include_inactive=true",{cache:"no-store"}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.message);return d}).then(setSkills).catch(()=>setMessage("暂时无法读取创作 Skill。"));useEffect(()=>{load()},[]);async function sync(id:string){setSyncing(id);setMessage("");try{const r=await fetch(`/api/playbooks/${id}/sync`,{method:"POST"}),d=await r.json();if(!r.ok)throw new Error(d.message);setMessage(d.updated?"已同步到最新版本。":"已经是最新版本。");load()}catch(e){setMessage(e instanceof Error?e.message:"同步失败。 ")}finally{setSyncing("")}}return <><section className="panel settings-panel"><h2>当前工作台</h2><dl><div><dt>运行方式</dt><dd>本机开发预览 · 不用于公网</dd></div><div><dt>数据保存</dt><dd>当前电脑的本地数据库 · 已保存内容可备份</dd></div><div><dt>第三方凭证</dt><dd>在本机后端配置，页面不展示密钥</dd></div></dl></section><LocalSettings/><CustomPlaybookForm onCreated={load}/><RegisterPlaybook onCreated={load}/><section className="panel skill-settings"><div className="section-heading"><div><h2>创作 Skill 管理</h2><p>同步后，后续生成使用最新版本；已有生成记录保留当时版本，已生成方向沿用当时配置。</p>{message&&<p className="provider-message">{message}</p>}</div></div>{skills.map(skill=><div className="skill-row" key={skill.id}><div><strong>{skill.name}</strong><span>{skill.repository_url||"本机自定义 Skill"}</span><small>版本 {skill.revision?.slice(0,8)} · 上次同步 {new Date(skill.synced_at).toLocaleString("zh-CN")}</small></div><PlaybookRouting id={skill.id}/><PlaybookToggle id={skill.id} name={skill.name} enabled={skill.status==="ACTIVE"} onChanged={load}/>{skill.source_type==="custom"&&<EditPlaybook id={skill.id} onSaved={load}/>} {skill.repository_url&&<Button variant="outline" disabled={syncing===skill.id} onClick={()=>sync(skill.id)}>{syncing===skill.id?<LoaderCircle className="spin" size={14}/>:null}同步</Button>}</div>)}</section></>}

export function WorkspacePage({ section }: { section: string }) {
  const add = useContext(AddContext);
  return <><Heading section={section} />
    {section === "today" ? <DailyBrief/> : section === "works" ? <WorkLibrary />
    : section === "creation" ? <CreationSpace />
    : section === "tasks" ? <TaskCenter />
    : section === "settings" ? <SettingsPanel />
    : section === "creators" ? <CreatorMonitor/>
    : <CreatorFeed/>}
    <div className="scope-footer"><CircleDot size={14} /><span>本地工作台：创作者每日检查、作品收录、逐字稿、分析和 Skill 创作。账户与云端持续运行尚未接入。</span></div>
  </>;
}
