"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CreatorFeed } from "@/components/creator-monitor";
type Detail={creator:{id:string;name:string;source_url:string;daily:boolean;status:string;last_checked_at:string|null;next_check_at:string;error_summary:string|null};stats:{works:number;transcripts:number;analyses:number}};
export function CreatorDetail({creatorId}:{creatorId:string}){
 const [item,setItem]=useState<Detail|null>(null),[error,setError]=useState('');
 useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;async function load(){try{const r=await fetch('/api/creators/'+encodeURIComponent(creatorId),{cache:'no-store',signal:controller.signal});const d=await r.json();if(!r.ok)throw new Error(d.message||'读取失败');if(!controller.signal.aborted){setItem(d);setError('')}}catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'读取失败')}finally{if(!controller.signal.aborted)timer=setTimeout(load,10000)}}void load();return()=>{controller.abort();clearTimeout(timer)}},[creatorId]);
 const creator=item?.creator;
 return <><Link href="/creators" className="back-link">返回对标创作者</Link>{error&&<p role="alert">{error}</p>}{creator&&item?<><section className="panel creator-form"><h1>{creator.name}</h1><p>抖音 · {creator.daily?'每日自动检查':'自动检查已暂停'} · {creator.status==='BLOCKED'?'接口需处理，自动检查已阻断':creator.status==='FAILED'?'上次检查失败':creator.status==='PROCESSING'?'检查中':'已收录'}</p><p>已收录 {item.stats.works} 条 · 已完成逐字稿 {item.stats.transcripts} 条 · 已完成分析 {item.stats.analyses} 条</p><p>上次完成：{creator.last_checked_at?new Date(creator.last_checked_at).toLocaleString('zh-CN'):'暂无'}{creator.daily&&creator.status!=='BLOCKED'?' · 下次计划：'+new Date(creator.next_check_at).toLocaleString('zh-CN'):''}</p>{creator.error_summary&&<p className="task-error">{creator.error_summary}</p>}<div className="editor-actions"><a href={creator.source_url} target="_blank" rel="noreferrer">打开平台主页</a><Link href="/creators">调整每日检查 / 手动更新</Link></div></section><CreatorFeed creatorId={creatorId}/></>:!error&&<p>正在读取创作者…</p>}</>;
}
