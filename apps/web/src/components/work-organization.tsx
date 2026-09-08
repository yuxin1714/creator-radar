"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
export type WorkPreferences={favorite:boolean;archived:boolean;tags:string[];revision:number};
export const emptyPreferences:WorkPreferences={favorite:false,archived:false,tags:[],revision:0};
export function WorkOrganization({workId,initial=emptyPreferences,onSaved}:{workId:string;initial?:WorkPreferences;onSaved?:(value:WorkPreferences)=>void}){
 const [favorite,setFavorite]=useState(initial.favorite),[archived,setArchived]=useState(initial.archived),[tags,setTags]=useState(initial.tags.join('，')),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[saved,setSaved]=useState(initial);
 const [storageError,setStorageError]=useState(''),[restored,setRestored]=useState(false),[stale,setStale]=useState(false);
 const [draftRevision,setDraftRevision]=useState(initial.revision);
 const cacheKey=`creator-radar:work-management:v1:${workId}`;
 useEffect(()=>{
  setSaved(initial);setFavorite(initial.favorite);setArchived(initial.archived);setTags(initial.tags.join('，'));setRestored(false);setStale(false);setDraftRevision(saved.revision);setDraftRevision(initial.revision);
  try{
   const raw=sessionStorage.getItem(cacheKey);if(!raw)return;
   const draft=JSON.parse(raw);
   if(typeof draft.favorite!=='boolean'||typeof draft.archived!=='boolean'||typeof draft.tags!=='string'||draft.tags.length>1000||!Number.isInteger(draft.revision))return;
   setFavorite(draft.favorite);setArchived(draft.archived);setTags(draft.tags);setRestored(true);setStale(draft.revision!==initial.revision);setDraftRevision(draft.revision);
  }catch{setStorageError('浏览器暂存不可用，请先复制保留标签。');}
 },[initial.revision,workId]);
 function remember(changes:Partial<{favorite:boolean;archived:boolean;tags:string}>,revision=draftRevision){
  const next={favorite,archived,tags,...changes};setFavorite(next.favorite);setArchived(next.archived);setTags(next.tags);
  setDraftRevision(revision);
  try{sessionStorage.setItem(cacheKey,JSON.stringify({...next,revision}));setStorageError('');}
  catch{setStorageError('浏览器暂存不可用，请先复制保留标签。');}
 }
 function discard(){
  setFavorite(saved.favorite);setArchived(saved.archived);setTags(saved.tags.join('，'));setRestored(false);setStale(false);
  try{sessionStorage.removeItem(cacheKey);setStorageError('');}catch{setStorageError('无法清除浏览器暂存。');}
 }
 async function save(){setBusy(true);setMessage('');try{
  const r=await fetch(`/api/works/${encodeURIComponent(workId)}/preferences`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({favorite,archived,tags:tags.split(/[，,;；\n]/).map(v=>v.trim()).filter(Boolean),expected_revision:saved.revision})});const d=await r.json();if(!r.ok)throw new Error(d.message||'保存失败');setSaved(d);setFavorite(d.favorite);setArchived(d.archived);setTags(d.tags.join('，'));setRestored(false);setStale(false);setDraftRevision(d.revision);setMessage('管理设置已保存。');try{sessionStorage.removeItem(cacheKey)}catch{setStorageError('设置已保存，但暂存未能清除。');}onSaved?.(d);
 }catch(e){setMessage(e instanceof Error?e.message:'保存失败')}finally{setBusy(false)}}
 return <details className="work-organization"><summary>{saved.favorite?'★ 已收藏 · ':''}{saved.archived?'已归档 · ':''}管理作品</summary><div>{restored&&<p role="status">已恢复未提交的管理设置。{stale?'其他页面已更新，请对照后确认。':''}</p>}{stale&&<><p>最新标签：{saved.tags.join('，')||'无'} · 收藏：{saved.favorite?'是':'否'} · 归档：{saved.archived?'是':'否'}</p><Button variant="outline" onClick={()=>{setStale(false);remember({},saved.revision);}}>已对照，保留当前填写</Button></>}<fieldset disabled={busy}><label><input type="checkbox" checked={favorite} onChange={e=>remember({favorite:e.target.checked})}/>收藏</label><label><input type="checkbox" checked={archived} onChange={e=>remember({archived:e.target.checked})}/>归档（仍可恢复）</label><label>标签<input aria-label="作品标签" value={tags} maxLength={1000} onChange={e=>remember({tags:e.target.value})} placeholder="标签以逗号分隔，最多 12 个"/></label></fieldset><small>输入暂存在当前标签页；保存后才会生效。</small><Button variant="outline" disabled={busy||stale} onClick={()=>void save()}>{busy?'保存中…':'保存管理设置'}</Button><Button variant="ghost" disabled={busy} onClick={discard}>还原已保存设置</Button>{storageError&&<p role="alert">{storageError}</p>}{message&&<p role="status">{message}</p>}</div></details>;
}
