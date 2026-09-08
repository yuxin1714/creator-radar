"use client";
import { useState } from "react";
import Markdown from "react-markdown";
import { Button } from "@/components/ui/button";
export function DraftPreview({content}:{content:string}){
 const [source,setSource]=useState(false);
 return <section className="draft-preview"><Button variant="ghost" onClick={()=>setSource(v=>!v)}>{source?'阅读预览':'查看原文'}</Button>{source?<pre>{content}</pre>:<div className="draft-markdown"><Markdown skipHtml components={{img:({alt})=><span>［图片：{alt||'未命名'}］</span>,a:({href,children})=><a href={href} target="_blank" rel="noreferrer">{children}</a>}}>{content}</Markdown></div>}</section>;
}
