import { NextRequest, NextResponse } from "next/server";
export async function POST(request: NextRequest) {
  const origin=request.headers.get("origin"), host=request.headers.get("host");
  if(origin && !["http://"+host,"https://"+host].includes(origin)) return NextResponse.json({message:"请在工作台内提交。"}, {status:403});
  try {
    const raw=await request.text(); if(raw.length>6000) return NextResponse.json({message:"请求过长。"}, {status:413});
    const body=JSON.parse(raw); if(!body || typeof body!=="object") return NextResponse.json({message:"输入格式不正确。"}, {status:422});
    const response=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+"/api/v1/imports",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:AbortSignal.timeout(10000),cache:"no-store"});
    return NextResponse.json(await response.json(),{status:response.status});
  } catch { return NextResponse.json({message:"暂时连接不到导入服务。"}, {status:503}); }
}