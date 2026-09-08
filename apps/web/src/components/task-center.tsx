"use client";
import Link from "next/link";
import { Pagination,emptyPage,type PageInfo } from "@/components/pagination";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

type Task = {id:string;kind:string;title:string;stage:string;status:string;error_summary:string|null;created_at:string;href:string};
const kinds:Record<string,string>={research:"译稿 / 多语分析",monitor:"主页更新检查",metadata:"元数据采集",transcript:"逐字稿转写",analysis:"内容分析",creation:"创作生成"};
const stages:Record<string,string>={"translation_en":"英文译稿","translation_zh-CN":"中文译稿","analysis_en":"英文分析","analysis_zh-CN":"中文分析",draft:"正文生成",directions:"创作方向",refine:"反馈优化",WAITING_PROVIDER:"等待数据服务",FETCHING_METADATA:"采集元数据",METADATA_READY:"元数据就绪"};
const statuses:Record<string,string>={PENDING:"待处理",PROCESSING:"处理中",COMPLETED:"完成",FAILED:"失败",BLOCKED:"接口需处理"};
export function TaskCenter(){
 const [page,setPage]=useState(1),[pageInfo,setPageInfo]=useState<PageInfo>(emptyPage);
 const [items,setItems]=useState<Task[]>([]),[error,setError]=useState(""),[loading,setLoading]=useState(true),[filter,setFilter]=useState("all"),[busy,setBusy]=useState<string|null>(null),[message,setMessage]=useState(""),[refresh,setRefresh]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  async function load(){try{
   const r=await fetch('/api/tasks?'+new URLSearchParams({page:String(page),status:filter}),{cache:'no-store',signal:controller.signal});const response=await r.json();const data=Array.isArray(response)?response:response.items;
   if(!r.ok)throw new Error(response.message||'任务读取失败');
   if(!Array.isArray(data))throw new Error('任务数据格式异常');
   if(!controller.signal.aborted){setPageInfo(Array.isArray(response)?{...emptyPage,total:data.length}:response);setItems(data);setError('');setLoading(false);}
  }catch(e){if(!controller.signal.aborted){setError(e instanceof Error?e.message:'任务读取失败');setLoading(false);}}
  finally{if(!controller.signal.aborted)timer=setTimeout(load,5000);}}
  void load();return()=>{controller.abort();clearTimeout(timer)};
 },[refresh,page,filter]);
 async function run(item:Task){setBusy(item.id);setMessage('');try{
  const r=await fetch(`/api/tasks/${encodeURIComponent(item.id)}/${item.status==='FAILED'?'retry':'run'}`,{method:'POST'});const data=await r.json();
  setMessage(data.message||(r.ok?'处理请求完成。':'任务请求失败。'));setRefresh(v=>v+1);
 }catch{setMessage('无法连接服务，请刷新检查任务状态。')}finally{setBusy(null)}}
 const shown=items.filter(item=>filter==='all'||filter==='active'&&['PENDING','PROCESSING'].includes(item.status)||filter===item.status||filter==='FAILED'&&item.status==='BLOCKED');
 return <section className="panel"><div className="section-heading"><div><h2>任务中心</h2><p>分页查看采集、转写、分析和创作任务，每 5 秒刷新。进入对应作品或项目查看结果及重新发起任务。</p></div><Button variant="outline" onClick={()=>setRefresh(v=>v+1)}>刷新任务</Button></div><label className="task-filter">任务状态<select aria-label="任务状态" value={filter} onChange={e=>{setPage(1);setFilter(e.target.value)}}><option value="all">全部</option><option value="active">待处理 / 处理中</option><option value="FAILED">失败</option><option value="COMPLETED">完成</option></select></label>{message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}{loading?<p>正在读取任务…</p>:!shown.length?<p>当前筛选下没有任务。</p>:<div className="data-list">{shown.map(item=><div className="data-row" key={`${item.kind}:${item.id}`}><div><strong>{item.title}</strong><span>{kinds[item.kind]||item.kind} · {new Date(item.created_at).toLocaleString('zh-CN')}</span>{item.error_summary&&<span className="task-error">{item.error_summary}</span>}</div><span>{stages[item.stage]||kinds[item.kind]||item.stage}</span><div><Link href={item.href}>查看详情</Link>{item.kind==='metadata'&&['PENDING','FAILED'].includes(item.status)&&<Button variant="outline" disabled={busy!==null} onClick={()=>void run(item)}>{busy===item.id?'提交中…':item.status==='FAILED'?'重试采集':'开始采集'}</Button>}</div><span className="status-pill">{statuses[item.status]||item.status}</span></div>)}</div>}<Pagination info={pageInfo} busy={loading} onPage={setPage}/></section>;
}
