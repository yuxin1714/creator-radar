"use client";
import { DraftPreview } from "@/components/draft-preview";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { CreationDirections } from "@/components/creation-directions";
type Generation={id:string;mode:string;status:string;content:string|null;error_summary:string|null;created_at:string;playbook_id:string;playbook_revision:string|null};
const modes:Record<string,string>={draft:"正文生成",directions:"创作方向",refine:"反馈优化"};
export function GenerationHistory({projectId,refresh,disabled,onAdopt,onChoose}:{projectId:string;refresh:string;disabled:boolean;onAdopt:(content:string)=>void;onChoose:(id:string,index:number)=>void}){
 const [open,setOpen]=useState(false),[items,setItems]=useState<Generation[]>([]),[selected,setSelected]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(false);
 useEffect(()=>{if(new URLSearchParams(window.location.search).has('generation'))setOpen(true)},[projectId]);
 useEffect(()=>{
  if(!open)return;const controller=new AbortController();setLoading(true);setError('');
  async function load(){try{
   const base=`/api/creation-projects/${encodeURIComponent(projectId)}/generations`;
   const r=await fetch(base,{cache:'no-store',signal:controller.signal});const data=await r.json();if(!r.ok||!Array.isArray(data))throw new Error(data.message||'读取失败');
   const target=new URLSearchParams(window.location.search).get('generation');
   if(target&&!data.some((g:Generation)=>g.id===target)){
    const tr=await fetch(base+'?generation_id='+encodeURIComponent(target),{cache:'no-store',signal:controller.signal});const extra=await tr.json();
    if(!tr.ok||!Array.isArray(extra))throw new Error('无法读取指定生成记录');
    if(!extra.length)throw new Error('指定生成记录不存在或不属于此项目');data.push(...extra);
   }
   if(!controller.signal.aborted){setItems(data);setSelected(current=>data.some((g:Generation)=>g.id===current)?current:target||data[0]?.id||'');}
  }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'读取失败')}
  finally{if(!controller.signal.aborted)setLoading(false)}}
  void load();return()=>controller.abort();
 },[projectId,open,refresh]);
 const item=items.find(i=>i.id===selected);
 return <details className="draft-history" open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>生成历史</summary>{loading?<p>正在读取生成记录…</p>:error?<p role="alert">{error}</p>:!items.length?<p>暂无生成记录。</p>:<><label>最近 50 次生成<select aria-label="生成记录" value={selected} onChange={e=>setSelected(e.target.value)}>{items.map(i=><option key={i.id} value={i.id}>{new Date(i.created_at).toLocaleString('zh-CN')} · {modes[i.mode]||i.mode} · {i.status==='COMPLETED'?'完成':i.status==='FAILED'?'失败':'处理中'}</option>)}</select></label>{item&&<div className="history-preview"><p>Skill {item.playbook_id} · {item.playbook_revision||'版本未记录'}</p>{item.error_summary&&<p role="alert">{item.error_summary}</p>}{item.status==='COMPLETED'&&item.content&&(item.mode==='directions'?<CreationDirections content={item.content} disabled={disabled} onChoose={index=>onChoose(item.id,index)}/>:<><DraftPreview content={item.content}/><Button variant="outline" disabled={disabled} onClick={()=>onAdopt(item.content!)}>载入此生成稿</Button><p>载入仅替换编辑器，保存后写入草稿版本。</p></>)}</div>}</>}</details>;
}
