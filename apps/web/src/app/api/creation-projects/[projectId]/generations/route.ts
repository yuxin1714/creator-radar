import { NextResponse } from "next/server";
export async function GET(request:Request,{params}:{params:Promise<{projectId:string}>}) {
  const {projectId}=await params;
  const query=new URLSearchParams(),id=new URL(request.url).searchParams.get("generation_id");
  if(id)query.set("generation_id",id);
  for(const key of ["page","page_size"])if(new URL(request.url).searchParams.has(key))query.set(key,new URL(request.url).searchParams.get(key)!);
  try{
    const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+`/api/v1/creation-projects/${encodeURIComponent(projectId)}/generations?${query}`,{cache:"no-store",signal:AbortSignal.timeout(10000)});
    return NextResponse.json(await r.json(),{status:r.status});
  }catch{return NextResponse.json({message:"暂时无法读取生成历史。"},{status:503});}
}
export async function POST(request:Request,{params}:{params:Promise<{projectId:string}>}) {
  const origin=request.headers.get("origin");
  // Next may normalize request.url to localhost while the browser uses 127.0.0.1.
  const host=request.headers.get("host")||new URL(request.url).host;
  if(origin&&origin!==`${new URL(request.url).protocol}//${host}`)return NextResponse.json({message:"请求来源无效。"},{status:403});
  const {projectId}=await params;
  let options;
  try { const text=await request.text(); options=text?JSON.parse(text):{}; }
  catch {return NextResponse.json({message:"生成选项格式无效。"},{status:400});}
  try {
    const r=await fetch((process.env.API_INTERNAL_BASE_URL??"http://127.0.0.1:8000")+`/api/v1/creation-projects/${encodeURIComponent(projectId)}/generations`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(options),signal:AbortSignal.timeout(15000)});
    const data=await r.json();
    return NextResponse.json(r.ok?data:{message:data.message||"生成请求未通过校验，请检查创作选项。"},{status:r.status});
  }catch{return NextResponse.json({message:"API 暂时不可用。"},{status:503});}
}
