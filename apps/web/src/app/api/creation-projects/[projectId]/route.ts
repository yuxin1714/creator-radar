import { NextResponse } from "next/server";
const base = () => process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
async function proxy(request: Request, projectId: string, method: string) { try { const r=await fetch(base()+`/api/v1/creation-projects/${encodeURIComponent(projectId)}`,{method,headers:method==="PATCH"?{"content-type":"application/json"}:undefined,body:method==="PATCH"?JSON.stringify(await request.json()):undefined,cache:"no-store"}); return NextResponse.json(await r.json(),{status:r.status}); } catch { return NextResponse.json({message:"API 暂时不可用。"},{status:503}); } }
export async function GET(request:Request,{params}:{params:Promise<{projectId:string}>}){return proxy(request,(await params).projectId,"GET")}
export async function PATCH(request:Request,{params}:{params:Promise<{projectId:string}>}){return proxy(request,(await params).projectId,"PATCH")}
