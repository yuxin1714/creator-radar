"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
const fields={platforms:[['tiktok','TikTok'],['instagram','Instagram'],['x','X'],['douyin','抖音'],['xiaohongshu','小红书']],content_types:[['knowledge','知识科普'],['technology','技术解读'],['business','商业产品'],['commentary','观点评论'],['story','故事案例'],['tutorial','教程']],directions:[['structure_borrowing','结构借鉴'],['opinion_reverse','观点反向'],['cross_domain','跨领域迁移'],['deep_expand','深度扩展'],['platform_adapt','平台改写']],styles:[['professional','理性专业'],['friendly','朋友式讲解'],['sharp','强观点'],['storytelling','故事化'],['concise','极简']]};
const labels={platforms:'平台',content_types:'内容类型',directions:'创作方向',styles:'表达风格'};
type Criteria=Record<keyof typeof fields,string[]>;
export function PlaybookRouting({id}:{id:string}){
 const dialog=useRef<HTMLDialogElement>(null),[criteria,setCriteria]=useState<Criteria|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function open(){dialog.current?.showModal();setCriteria(null);setError('');try{const r=await fetch('/api/playbook-routing/'+encodeURIComponent(id));const d=await r.json();if(!r.ok)throw new Error(d.message);setCriteria(d)}catch(e){setError(e instanceof Error?e.message:'读取失败')}}
 async function save(){setBusy(true);try{const r=await fetch('/api/playbook-routing/'+encodeURIComponent(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(criteria)});const d=await r.json();if(!r.ok)throw new Error(d.message);dialog.current?.close()}catch(e){setError(e instanceof Error?e.message:'保存失败')}finally{setBusy(false)}}
 return <><Button variant="outline" onClick={()=>void open()}>匹配条件</Button><dialog ref={dialog} className="add-dialog" aria-label="Skill 匹配条件"><div className="dialog-top"><h2>Skill 匹配条件</h2><Button variant="ghost" onClick={()=>dialog.current?.close()}>关闭</Button></div><p>同一组内满足任一项，组与组之间须全部满足。留空表示不限；全部留空则仅供手动选择。条件越具体，匹配时越优先。</p>{error&&<p role="alert">{error}</p>}{criteria?<div className="creation-form">{(Object.keys(fields) as (keyof Criteria)[]).map(key=><fieldset key={key}><legend>{labels[key]}</legend>{fields[key].map(([value,label])=><label key={value}><input type="checkbox" checked={criteria[key].includes(value)} onChange={e=>setCriteria({...criteria,[key]:e.target.checked?[...criteria[key],value]:criteria[key].filter(v=>v!==value)})}/>{label}</label>)}</fieldset>)}<Button disabled={busy} onClick={()=>void save()}>保存匹配条件</Button></div>:<p>正在读取条件…</p>}</dialog></>;
}
export function MatchingPreview({platform,contentType,direction,style}:{platform:string;contentType:string;direction:string;style:string}){
 const [name,setName]=useState(''),[error,setError]=useState('');
 useEffect(()=>{const controller=new AbortController();setName('');setError('');const query=new URLSearchParams({platform,content_type:contentType,direction,style});fetch('/api/playbook-matching?'+query,{cache:'no-store',signal:controller.signal}).then(async r=>{const d=await r.json();if(!r.ok)throw new Error(d.message);if(!controller.signal.aborted)setName(d[0]?.name||'无可用匹配')}).catch(e=>{if(!controller.signal.aborted)setError(e.message)});return()=>controller.abort()},[platform,contentType,direction,style]);
 return <p className="quiet-note">{error||'当前匹配：'+(name||'正在匹配…')}。生成时会重新确认可用 Skill，并固定实际版本；没有专用匹配时使用通用结构借鉴。</p>;
}
