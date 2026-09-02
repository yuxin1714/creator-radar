"use client";

import Link from "next/link";
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
    <p className="eyebrow">ADD TO YOUR RADAR</p><h2 id="add-title">从一条作品链接开始</h2>
    <p className="dialog-description">粘贴作品地址或分享文字，先确认平台与作品标识。</p>
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
    </form>
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
  return <div className="page-heading"><div><p className="eyebrow">{section === "today" ? "YOUR DAILY CREATIVE BRIEF" : "YOUR CREATIVE WORKSPACE"}</p><h1>{data.title}</h1><p>{data.description}</p></div><span className="phase-tag">P0 · 作品导入基础</span></div>;
}

type WorkItem = { id:string; platform:keyof typeof platformNames; external_id:string; source_url:string; title:string|null; status:string; metadata:{author_name:string|null}|null; created_at:string };
type TaskItem = { id:string; platform:keyof typeof platformNames; external_id:string; stage:string; status:string; error_summary:string|null; created_at:string };
function useCollection<T>(url:string) {
  const [items,setItems]=useState<T[]>([]); const [loading,setLoading]=useState(true); const [error,setError]=useState("");
  useEffect(()=>{ let active=true; const load=async()=>{setLoading(true);try{const r=await fetch(url,{cache:"no-store"});const d=await r.json();if(!r.ok)throw new Error(d.message);if(active){setItems(d);setError("");}}catch(e){if(active)setError(e instanceof Error?e.message:"读取失败");}finally{if(active)setLoading(false);}};load();window.addEventListener("creator-radar:refresh",load);return()=>{active=false;window.removeEventListener("creator-radar:refresh",load)};},[url]);
  return {items,loading,error};
}
function WorksPanel(){const {items,loading,error}=useCollection<WorkItem>("/api/works");return <section className="panel"><div className="section-heading"><div><h2>全部作品 <span className="neutral-label">{items.length}</span></h2><p>已确认保存的外部作品；配置数据服务后可补全基础元数据。</p></div><AddButton /></div><div className="table-head"><span>作品 / 来源</span><span>平台</span><span>作者</span><span>处理状态</span></div>{error?<Empty icon={<FolderOpen size={28}/>} title="暂时无法读取作品库" description={error}/>:loading?<div className="list-loading"><LoaderCircle className="spin"/>正在读取…</div>:items.length?<div className="data-list">{items.map(item=><div className="data-row" key={item.id}><div><Link className="work-title-link" href={`/works/${item.id}`}>{item.title||`作品 ${item.external_id}`}</Link><span className="row-links"><Link href={`/works/${item.id}`}>查看详情</Link><a href={item.source_url} target="_blank" rel="noreferrer">原作品<ArrowUpRight size={13}/></a></span></div><span>{platformNames[item.platform]}</span><span>{item.metadata?.author_name||"—"}</span><span className={"status-pill "+(item.status==="READY"?"":"waiting")}>{item.status==="READY"?"元数据已就绪":"等待采集"}</span></div>)}</div>:<Empty icon={<FolderOpen size={28}/>} title="把值得研究的内容留在这里" description="验证平台响应后，确认导入的作品会出现在这里。"/>}</section>}
function TasksPanel(){const {items,loading,error}=useCollection<TaskItem>("/api/tasks");const [message,setMessage]=useState("");const [running,setRunning]=useState("");async function run(id:string,retry=false){setRunning(id);setMessage("");try{const r=await fetch(`/api/tasks/${id}/${retry?"retry":"run"}`,{method:"POST"});const d=await r.json();setMessage(d.message||(r.ok?"任务已完成。":"任务未能启动。"));window.dispatchEvent(new Event("creator-radar:refresh"));}catch{setMessage("暂时无法启动任务。");}finally{setRunning("");}}return <section className="panel"><div className="section-heading"><div><h2>系统处理任务 <span className="neutral-label">{items.length}</span></h2><p>任务只展示真实状态；当前首选元数据服务为 TikHub。</p>{message&&<p className="provider-message">{message}</p>}</div></div><div className="table-head"><span>任务 / 来源</span><span>当前阶段</span><span>操作</span><span>状态</span></div>{error?<Empty icon={<Workflow size={28}/>} title="暂时无法读取任务" description={error}/>:loading?<div className="list-loading"><LoaderCircle className="spin"/>正在读取…</div>:items.length?<div className="data-list">{items.map(item=><div className="data-row" key={item.id}><div><strong>{platformNames[item.platform]} 作品</strong><span className="mono">{item.external_id}</span>{item.error_summary&&<span className="task-error">{item.error_summary}</span>}</div><span>{item.stage==="METADATA_READY"?"元数据已就绪":item.stage==="FETCHING_METADATA"?"采集元数据":"等待数据服务"}</span><Button variant="outline" disabled={running===item.id||item.status==="COMPLETED"} onClick={()=>run(item.id,item.status==="FAILED")}>{running===item.id?<LoaderCircle className="spin" size={14}/>:null}{item.status==="COMPLETED"?"已完成":item.status==="FAILED"?"重试":"尝试采集"}</Button><span className={"status-pill "+(item.status==="COMPLETED"?"":"waiting")}>{item.status==="COMPLETED"?"完成":item.status==="FAILED"?"失败":"待处理"}</span></div>)}</div>:<Empty icon={<Workflow size={28}/>} title="没有正在处理的任务" description="确认导入作品后，这里会创建真实的等待处理任务。"/>}</section>}
function CreationPanel(){const [items,setItems]=useState<Array<{id:string;title:string;idea:string|null;status:string;updated_at:string}>>([]),[title,setTitle]=useState(""),[idea,setIdea]=useState(""),[busy,setBusy]=useState(false),[message,setMessage]=useState("");const load=()=>fetch("/api/creation-projects",{cache:"no-store"}).then(r=>r.json()).then(setItems).catch(()=>setMessage("暂时无法读取创作项目。"));useEffect(()=>{load()},[]);async function create(){if(!title.trim())return;setBusy(true);setMessage("");try{const r=await fetch("/api/creation-projects",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({title,idea:idea||null})});const d=await r.json();if(!r.ok)throw new Error(d.message);setTitle("");setIdea("");setMessage("草稿项目已创建。");load()}catch(e){setMessage(e instanceof Error?e.message:"无法创建项目。")}finally{setBusy(false)}}return <><section className="panel"><div className="section-heading"><div><h2>创作空间</h2><p>保存自己的想法和草稿，不与外部参考作品混淆。</p></div><span className="neutral-label">草稿模式</span></div><div className="creation-form"><input aria-label="项目标题" placeholder="项目标题" value={title} onChange={e=>setTitle(e.target.value)}/><textarea aria-label="创作想法" placeholder="先记录一个想法（可选）" value={idea} onChange={e=>setIdea(e.target.value)}/><Button disabled={busy||!title.trim()} onClick={create}>{busy?<LoaderCircle className="spin" size={15}/>:<Plus size={15}/>}新建草稿</Button>{message&&<p className="provider-message">{message}</p>}</div></section>{items.length?<section className="panel"><div className="section-heading"><div><h2>最近项目 <span className="neutral-label">{items.length}</span></h2></div></div><div className="data-list">{items.map(item=><div className="data-row creation-row" key={item.id}><div><strong>{item.title}</strong><span>{item.idea||"尚未记录内容"}</span></div><span>中文</span><span>{item.status}</span><span>{new Date(item.updated_at).toLocaleDateString("zh-CN")}</span></div>)}</div></section>:null}</>}

export function WorkspacePage({ section }: { section: string }) {
  const add = useContext(AddContext);
  return <><Heading section={section} />
    {section === "today" ? <>
      <section className="welcome-panel"><div className="welcome-copy"><span className="welcome-kicker"><Sparkles size={15} /> 每个好内容，都始于一次发现</span><h2>你的下一次创作，<br />从这里发现。</h2><p>把值得研究的作品带进工作台。<br />先验证一条链接，开始搭建你的内容雷达。</p><AddButton /><span className="welcome-footnote">抖音 / TikTok / YouTube</span></div><div className="radar-illustration" aria-hidden="true"><div className="radar-ring ring-one" /><div className="radar-ring ring-two" /><div className="radar-ring ring-three" /><div className="radar-line" /><span className="radar-center"><Radar size={34} /></span><span className="radar-node node-one"><FileText size={20} /></span><span className="radar-node node-two"><Globe2 size={20} /></span><span className="radar-node node-three"><Sparkles size={20} /></span><span className="radar-caption">DISCOVER · UNDERSTAND · CREATE</span></div></section>
      <div className="today-grid"><section className="panel"><div className="section-heading"><div><h2>今日精选<span className="neutral-label">尚未生成</span></h2><p>只保留值得你花时间的内容。</p></div><Link className="text-link" href="/feed">查看情报流<ArrowRight size={15} /></Link></div><Empty icon={<Compass size={28} />} title="你的雷达，等待第一条信号" description="接入作品采集与分析后，这里会呈现高价值内容及推荐依据。当前不展示模拟情报。" action={<Button variant="outline" onClick={add}>先验证一条链接<ArrowRight size={15} /></Button>} /></section>
      <aside className="panel first-steps"><p className="eyebrow">GET STARTED</p><h2>从发现到创作</h2><ol><li className="step-current"><span>01</span><div><strong>添加作品链接</strong><p>识别平台，验证作品地址。</p><button className="text-link" onClick={add}>立即验证<ArrowUpRight size={15} /></button></div></li><li><span>02</span><div><strong>理解内容价值</strong><p>采集、逐字稿与 AI 拆解待接入。</p></div></li><li><span>03</span><div><strong>开始自己的创作</strong><p>中文或英文，保存并继续编辑。</p></div></li></ol><div className="quiet-note"><ShieldCheck size={16} />当前验证不会调用付费服务。</div></aside></div>
    </> : section === "works" ? <WorksPanel />
    : section === "creation" ? <CreationPanel />
    : section === "tasks" ? <TasksPanel />
    : section === "settings" ? <section className="panel settings-panel"><h2>当前工作台</h2><dl><div><dt>运行方式</dt><dd>本机开发预览 · 不用于公网</dd></div><div><dt>本轮可用</dt><dd><Check size={16} />链接确认、作品持久化、元数据任务框架</dd></div><div><dt>支持的平台</dt><dd>抖音 / TikTok / YouTube</dd></div><div><dt>账户与持久化</dt><dd>PostgreSQL 本机数据 · 单一 local-user</dd></div><div><dt>元数据服务</dt><dd>TikHub 适配器已接入 · API Key 尚未配置</dd></div><div><dt>第三方凭证</dt><dd>仅在后端 .env 配置，不在页面填写或展示</dd></div></dl><div className="quiet-note"><ShieldCheck size={17} />未配置凭证时不会调用计费接口；媒体、分析与创作能力尚未接入。</div></section>
    : section === "creators" ? <section className="panel"><div className="section-heading"><div><h2>对标创作者</h2><p>持续关注更新，而不只是收藏一个账号。</p></div><span className="neutral-label">导入与监控待接入</span></div><Empty icon={<Users size={28} />} title="你关注的创作者，将在这里汇集" description="本轮只验证作品链接。创作者主页导入、作品获取与抖音监控留待后续开发。" /></section>
    : <section className="panel"><div className="section-heading"><div><h2>发现内容</h2><p>情报流用于探索，作品库用于管理已收集的内容。</p></div><span className="neutral-label">数据源待接入</span></div><Empty icon={<Rss size={28} />} title="让有价值的内容进入视野" description="平台内容接入后，你可以在这里主动探索作品。现在可以先验证一条已找到的作品链接。" action={<AddButton />} /></section>}
    <div className="scope-footer"><CircleDot size={14} /><span>当前版本：作品确认导入与元数据任务框架。TikHub 密钥、媒体、分析、创作及账户功能尚未接入。</span></div>
  </>;
}
