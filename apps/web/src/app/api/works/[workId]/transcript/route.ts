import { NextResponse } from "next/server";
export async function GET(_request:Request,{params}:{params:Promise<{workId:string}>}) {
  const {workId}=await params;
  try { const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+`/api/v1/works/${encodeURIComponent(workId)}/transcript`,{signal:AbortSignal.timeout(10000),cache:"no-store"}); return NextResponse.json(await r.json(),{status:r.status}); }
  catch { return NextResponse.json({message:"暂时无法读取逐字稿状态。"},{status:503}); }
}
export async function POST(_request:Request,{params}:{params:Promise<{workId:string}>}) {
  const {workId}=await params;
  try { const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+`/api/v1/works/${encodeURIComponent(workId)}/transcript`,{method:"POST",signal:AbortSignal.timeout(10000),cache:"no-store"}); return NextResponse.json(await r.json(),{status:r.status}); }
  catch { return NextResponse.json({message:"API 暂时不可用。"},{status:503}); }
}
