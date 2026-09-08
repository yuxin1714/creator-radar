"use client";
import Link from "next/link";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
type Creator={id:string;name:string;source_url:string;daily:boolean;status:string;error_summary:string|null;last_checked_at:string|null;next_check_at:string;last_new_count:number};
const time=(value:string|null)=>value?new Date(value).toLocaleString('zh-CN'):'尚未完成';
export function CreatorMonitor(){
 const [items,setItems]=useState<Creator[]>([]),[link,setLink]=useState(''),[daily,setDaily]=useState(true),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[epoch,setEpoch]=useState(0);
 useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function load(){try{const r=await fetch('/api/creators',{cache:'no-store',signal:controller.signal});const d=await r.json();if(!r.ok||!Array.isArray(d))throw new Error(d.message||'无法读取创作者');if(!controller.signal.aborted){setItems(d);setError('')}}catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'读取失败')}finally{if(!controller.signal.aborted)timer=setTimeout(load,5000)}}
  void load();return()=>{controller.abort();clearTimeout(timer)};
 },[epoch]);
 async function action(path:string,method:string,body?:unknown){setBusy(true);setMessage('');try{
  const r=await fetch('/api/creators'+path,{method,headers:{'content-type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(d.message||'操作失败');setMessage(d.message||'监控设置已保存。');setEpoch(v=>v+1);if(path==='')setLink('');
 }catch(e){setMessage(e instanceof Error?e.message:'请求失败')}finally{setBusy(false)}}
 return <><section className="panel creator-form"><h2>添加对标创作者</h2><p>支持抖音主页及主页分享短链接。首次收录近期一页作品；更新检查只获取作品信息，逐字稿与 AI 分析由你按需发起。</p><label>创作者主页<textarea aria-label="创作者主页" value={link} maxLength={4000} onChange={e=>setLink(e.target.value)} placeholder="粘贴抖音主页分享内容"/></label><label><input type="checkbox" checked={daily} onChange={e=>setDaily(e.target.checked)}/>每天自动检查一次</label><Button disabled={busy||!link.trim()} onClick={()=>void action('','POST',{text:link,daily})}>{busy?'提交中…':'添加主页'}</Button>{message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}<p className="quiet-note">自动检查需要本机工作台和数据库运行。停机后下次启动补查；每次检查调用已配置的 TikHub，最多获取三页，失败后次日再试。</p></section><section className="panel creator-list"><h2>关注的创作者 · {items.length}</h2>{!items.length?<p>尚未添加创作者。</p>:items.map(item=><article className="creator-card" key={item.id}><h3><Link href={`/creators/${item.id}`}>{item.name}</Link></h3><p>{item.status==='PROCESSING'?'正在检查更新':item.status==='FAILED'?'检查失败':item.status==='COMPLETED'?'检查完成':'等待首次检查'} · 上次新增收录 {item.last_new_count} 条</p><p>上次完成：{time(item.last_checked_at)} · {item.daily?'下次检查：'+time(item.next_check_at):'自动检查已暂停'}</p>{item.error_summary&&<p className="task-error">{item.error_summary}</p>}<div className="editor-actions"><Link href={`/feed?creator=${item.id}`}>查看已收录作品</Link><a href={item.source_url} target="_blank" rel="noreferrer">打开抖音主页</a><Button variant="outline" disabled={busy||item.status==='PROCESSING'} onClick={()=>void action('/'+item.id+'/check','POST')}>检查更新</Button><Button variant="outline" disabled={busy} onClick={()=>void action('/'+item.id,'PATCH',{daily:!item.daily})}>{item.daily?'暂停每日检查':'开启每日检查'}</Button></div></article>)}</section></>;
}
type FeedItem={id:string;title:string;creator_id:string;creator_name:string;discovered_at:string;published_at:string|null};
function FeedContent({today=false,creatorId}:{today?:boolean;creatorId?:string}){
 const search=useSearchParams(),creator=creatorId||(today?null:search.get('creator'));
 const [items,setItems]=useState<FeedItem[]>([]),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;setLoading(true);
  async function load(){try{const params=new URLSearchParams();if(today)params.set('today','true');if(creator)params.set('creator_id',creator);const r=await fetch('/api/feed?'+params,{cache:'no-store',signal:controller.signal});const d=await r.json();if(!r.ok||!Array.isArray(d))throw new Error(d.message||'读取失败');if(!controller.signal.aborted){setItems(d);setError('')}}catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'读取失败')}finally{if(!controller.signal.aborted){setLoading(false);timer=setTimeout(load,10000)}}}
  void load();return()=>{controller.abort();clearTimeout(timer)};
 },[today,creator]);
 return <section className="panel"><div className="section-heading"><div><h2>{today?'最近 24 小时新收录':'创作者情报流'}</h2><p>按收录时间排列，最多 200 条；收录时间不等于发布时间，不作未经分析的质量推荐。</p></div><Link href="/creators">管理创作者</Link></div>{creator&&<Link href="/feed">查看全部创作者</Link>}{error&&<p role="alert">{error}</p>}{loading?<p>正在读取情报…</p>:!items.length?<p>当前没有收录记录，添加主页后将显示真实作品。</p>:<div className="data-list">{items.map(item=><article className="data-row" key={item.creator_id+item.id}><div><Link href={`/works/${item.id}`}><strong>{item.title}</strong></Link><span>{item.creator_name}</span></div><span>发布：{time(item.published_at)}</span><span>收录：{time(item.discovered_at)}</span><Link href={`/works/${item.id}?tab=analysis`}>查看与分析</Link></article>)}</div>}</section>;
}
export function CreatorFeed({today=false,creatorId}:{today?:boolean;creatorId?:string}){return <Suspense fallback={<p>正在读取情报…</p>}><FeedContent today={today} creatorId={creatorId}/></Suspense>}
