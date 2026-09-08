"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
export function RegisterPlaybook({onCreated}:{onCreated:()=>void}){
 const [name,setName]=useState(''),[url,setUrl]=useState(''),[path,setPath]=useState('SKILL.md'),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setMessage('');try{
  const r=await fetch('/api/playbook-sources/remote',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name,repository_url:url,skill_path:path})});const d=await r.json();if(!r.ok)throw new Error(d.message||'注册失败');setMessage(d.message);onCreated();
 }catch(e){setMessage(e instanceof Error?e.message:'注册失败')}finally{setBusy(false)}}
 return <section className="panel"><div className="section-heading"><div><h2>添加 GitHub Skill</h2><p>注册后在下方列表点击同步。只读取 SKILL.md 及引用文档，不执行仓库代码；更新后再次同步即可使用新版本。</p></div></div><form className="creation-form" onSubmit={submit}><label>显示名称<input aria-label="远程 Skill 名称" required maxLength={200} value={name} onChange={e=>setName(e.target.value)}/></label><label>GitHub 仓库<input aria-label="Skill 仓库地址" required value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://github.com/用户名/仓库"/></label><label>仓库内路径<input aria-label="Skill 文件路径" required value={path} onChange={e=>setPath(e.target.value)} placeholder="目录/SKILL.md"/></label><Button type="submit" disabled={busy||!name.trim()||!url.trim()||!path.trim()}>{busy?'注册中…':'注册远程 Skill'}</Button>{message&&<p role="status">{message}</p>}</form></section>;
}
