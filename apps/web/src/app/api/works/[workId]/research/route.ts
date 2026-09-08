import { NextResponse } from "next/server";
type Context={params:Promise<{workId:string}>};
async function proxy(request:Request,{params}:Context){
 const {workId}=await params;const query=new URLSearchParams(),input=new URL(request.url).searchParams;
 for(const key of ['kind','language','run_id'])if(input.has(key))query.set(key,input.get(key)!);
 try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+`/api/v1/works/${encodeURIComponent(workId)}/research?${query}`,{method:request.method,headers:{'content-type':'application/json'},body:request.method==='POST'?JSON.stringify(await request.json()):undefined,cache:'no-store',signal:AbortSignal.timeout(15000)});const d=await r.json();return NextResponse.json(r.ok?d:{message:d.message||'研究任务参数无效。'},{status:r.status})}catch{return NextResponse.json({message:'研究服务暂时不可用，请稍后检查任务状态。'},{status:503})}
}
export const GET=proxy;export const POST=proxy;
