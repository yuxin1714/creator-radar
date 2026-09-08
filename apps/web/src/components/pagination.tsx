"use client";
import { Button } from "@/components/ui/button";
export type PageInfo={page:number;page_size:number;total:number;total_pages:number};
export const emptyPage:PageInfo={page:1,page_size:20,total:0,total_pages:1};
export function Pagination({info,busy=false,onPage}:{info:PageInfo;busy?:boolean;onPage:(page:number)=>void}){
 return <nav className="pagination" aria-label="分页"><span>共 {info.total} 条 · 第 {info.page} / {info.total_pages} 页</span><Button variant="outline" disabled={busy||info.page<=1} onClick={()=>onPage(info.page-1)}>上一页</Button><Button variant="outline" disabled={busy||info.page>=info.total_pages} onClick={()=>onPage(info.page+1)}>下一页</Button></nav>;
}
