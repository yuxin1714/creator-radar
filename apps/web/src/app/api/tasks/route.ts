import { NextResponse } from "next/server";
export async function GET() {
 try { const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+"/api/v1/tasks",{signal:AbortSignal.timeout(10000),cache:"no-store"}); return NextResponse.json(await r.json(),{status:r.status}); }
 catch { return NextResponse.json({message:"暂时无法读取任务。"}, {status:503}); }
}