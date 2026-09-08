"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
export function ProjectStatus({id,status,updatedAt,disabled,onChanged}:{id:string;status:string;updatedAt:string;disabled:boolean;onChanged:(data:{status:string;updated_at:string})=>void}){
 const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
 async function change(next:string){setBusy(true);setMessage('');try{const r=await fetch(`/api/creation-projects/${encodeURIComponent(id)}/status`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({status:next,expected_updated_at:updatedAt})});const d=await r.json();if(!r.ok)throw new Error(d.message);onChanged(d);setMessage('项目状态已更新。')}catch(e){setMessage(e instanceof Error?e.message:'更新失败')}finally{setBusy(false)}}
 return <section className="project-status"><p>项目状态：<strong>{status==='ARCHIVED'?'已归档':status==='COMPLETED'?'已完成':'草稿'}</strong>。{status==='ARCHIVED'?'归档保留正文与历史，可恢复为草稿。':'先保存当前修改再设置状态；修改完成稿并保存会回到草稿。'}</p><div className="editor-actions">{status!=='ARCHIVED'&&status!=='COMPLETED'&&<Button variant="outline" disabled={disabled||busy} onClick={()=>void change('COMPLETED')}>标记完成</Button>}{status!=='DRAFT'&&<Button variant="outline" disabled={disabled||busy} onClick={()=>void change('DRAFT')}>恢复为草稿</Button>}{status!=='ARCHIVED'&&<Button variant="ghost" disabled={disabled||busy} onClick={()=>void change('ARCHIVED')}>归档项目</Button>}{message&&<span role="status">{message}</span>}</div></section>;
}
