import { NextResponse } from "next/server";
type Context={params:Promise<{sourceId:string}>};
async function proxy(request:Request,{params}:Context){const {sourceId}=await params;try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+'/api/v1/playbook-updates/'+encodeURIComponent(sourceId),{method:request.method,headers:{'content-type':'application/json'},body:request.method==='PUT'?JSON.stringify(await request.json()):undefined,cache:'no-store',signal:AbortSignal.timeout(10000)});const d=await r.json();return NextResponse.json(r.ok?d:{message:d.message||'更新设置无效。'},{status:r.status})}catch{return NextResponse.json({message:'无法读取或保存更新计划。'},{status:503})}}
export const GET=proxy;export const PUT=proxy;
