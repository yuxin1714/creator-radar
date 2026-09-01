import { NextResponse } from "next/server";
export async function GET(_request:Request,{params}:{params:Promise<{workId:string}>}) {
  const {workId}=await params;
  try { const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+`/api/v1/works/${encodeURIComponent(workId)}/cover`,{signal:AbortSignal.timeout(25000)}); if(!r.ok)return NextResponse.json(await r.json(),{status:r.status}); return new NextResponse(await r.arrayBuffer(),{status:200,headers:{"Content-Type":r.headers.get("Content-Type")||"image/jpeg","Cache-Control":"private, max-age=3600","X-Content-Type-Options":"nosniff"}}); }
  catch { return NextResponse.json({message:"暂时无法读取封面。"},{status:503}); }
}
