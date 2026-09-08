"use client";
import { useEffect,useState } from "react";
import { Button } from "@/components/ui/button";
type Policy={enabled:boolean;revision:number;status:string;last_checked_at:string|null;next_check_at:string|null;error_summary:string|null};
const statusNames:Record<string,string>={IDLE:'等待检查',PROCESSING:'正在检查',CURRENT:'已是最新版本',UPDATED:'已更新到新版本',FAILED:'检查失败，旧版本保留',BLOCKED:'来源文档需处理'};
export function SkillUpdates({id}:{id:string}){
 const [item,setItem]=useState<Policy|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[epoch,setEpoch]=useState(0);
 useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;async function load(){try{const r=await fetch('/api/playbook-updates/'+encodeURIComponent(id),{cache:'no-store',signal:controller.signal});const d=await r.json();if(!r.ok)throw new Error(d.message);if(!controller.signal.aborted){setItem(d);setError('')}}catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'读取失败')}finally{if(!controller.signal.aborted)timer=setTimeout(load,5000)}}void load();return()=>{controller.abort();clearTimeout(timer)}},[id,epoch]);
 async function toggle(){if(!item)return;setBusy(true);setError('');try{const r=await fetch('/api/playbook-updates/'+encodeURIComponent(id),{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({enabled:!item.enabled,expected_revision:item.revision})});const d=await r.json();if(!r.ok)throw new Error(d.message);setItem(d);setEpoch(v=>v+1)}catch(e){setError(e instanceof Error?e.message:'保存失败')}finally{setBusy(false)}}
 return <div className="skill-updates">{item&&<><Button variant="ghost" disabled={busy} onClick={()=>void toggle()}>{item.enabled?'关闭每日更新检查':'开启每日更新检查'}</Button><small>{item.enabled?'每日自动检查 · '+(statusNames[item.status]||item.status):'手动同步模式'}{item.enabled&&item.next_check_at?' · 下次 '+new Date(item.next_check_at).toLocaleString('zh-CN'):''}</small>{item.last_checked_at&&<small>上次尝试：{new Date(item.last_checked_at).toLocaleString('zh-CN')}</small>}{item.error_summary&&<p role="status">{item.error_summary}</p>}</>}{error&&<p role="alert">{error}</p>}</div>;
}
