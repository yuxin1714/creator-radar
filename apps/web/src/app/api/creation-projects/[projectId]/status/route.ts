import { NextResponse } from "next/server";
export async function PATCH(request:Request,{params}:{params:Promise<{projectId:string}>}){
 const {projectId}=await params;
 try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+`/api/v1/creation-projects/${encodeURIComponent(projectId)}/status`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify(await request.json()),signal:AbortSignal.timeout(10000)});const d=await r.json();return NextResponse.json(r.ok?d:{message:d.message||'项目状态请求无效。'},{status:r.status})}catch{return NextResponse.json({message:'无法更新项目状态，请刷新检查结果。'},{status:503})}
}
