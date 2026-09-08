"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
export function CreatorImport({onCreated,initialText=''}:{onCreated?:()=>void;initialText?:string}){
 const [text,setText]=useState(initialText),[daily,setDaily]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 async function submit(e:React.FormEvent){e.preventDefault();setBusy(true);setMessage('');try{const r=await fetch('/api/creators',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text,daily})});const d=await r.json();if(!r.ok)throw new Error(d.message||'添加失败');setMessage(d.message);setText('');onCreated?.();window.dispatchEvent(new Event('creator-radar:refresh'))}catch(e){setMessage(e instanceof Error?e.message:'添加失败')}finally{setBusy(false)}}
 return <form className="creation-form" onSubmit={submit}><label>创作者主页<textarea aria-label="创作者主页" value={text} maxLength={4000} onChange={e=>setText(e.target.value)} placeholder="抖音主页地址或主页分享内容"/></label><label><input type="checkbox" checked={daily} onChange={e=>setDaily(e.target.checked)}/>开启每天自动检查</label><p>添加时会验证主页并收录近期作品，需要 TikHub 可用。每日检查需要本机服务运行，可稍后在创作者页面开启。</p><Button type="submit" disabled={busy||!text.trim()}>{busy?'正在添加…':'确认添加创作者'}</Button>{message&&<p role="status">{message}</p>}</form>;
}
