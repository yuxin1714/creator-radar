"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
export type WorkPreferences={favorite:boolean;archived:boolean;tags:string[];revision:number};
export const emptyPreferences:WorkPreferences={favorite:false,archived:false,tags:[],revision:0};
export function WorkOrganization({workId,initial=emptyPreferences,onSaved}:{workId:string;initial?:WorkPreferences;onSaved?:(value:WorkPreferences)=>void}){
 const [favorite,setFavorite]=useState(initial.favorite),[archived,setArchived]=useState(initial.archived),[tags,setTags]=useState(initial.tags.join('，')),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[saved,setSaved]=useState(initial);
 useEffect(()=>{setSaved(initial);setFavorite(initial.favorite);setArchived(initial.archived);setTags(initial.tags.join('，'))},[initial.revision,workId]);
 async function save(){setBusy(true);setMessage('');try{
  const r=await fetch(`/api/works/${encodeURIComponent(workId)}/preferences`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({favorite,archived,tags:tags.split(/[，,;；\n]/).map(v=>v.trim()).filter(Boolean),expected_revision:saved.revision})});const d=await r.json();if(!r.ok)throw new Error(d.message||'保存失败');setSaved(d);setMessage('管理设置已保存。');onSaved?.(d);
 }catch(e){setMessage(e instanceof Error?e.message:'保存失败')}finally{setBusy(false)}}
 return <details className="work-organization"><summary>{saved.favorite?'★ 已收藏 · ':''}{saved.archived?'已归档 · ':''}管理作品</summary><div><label><input type="checkbox" checked={favorite} onChange={e=>setFavorite(e.target.checked)}/>收藏</label><label><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>归档（仍可恢复）</label><label>标签<input aria-label="作品标签" value={tags} onChange={e=>setTags(e.target.value)} placeholder="标签以逗号分隔，最多 12 个"/></label><Button variant="outline" disabled={busy} onClick={()=>void save()}>{busy?'保存中…':'保存管理设置'}</Button>{message&&<p role="status">{message}</p>}</div></details>;
}
