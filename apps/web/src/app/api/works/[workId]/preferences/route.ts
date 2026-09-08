import { NextResponse } from "next/server";
export async function PATCH(request:Request,{params}:{params:Promise<{workId:string}>}){
 const {workId}=await params;
 const origin=request.headers.get('origin'),host=request.headers.get('host')||new URL(request.url).host;
 if(origin&&origin!==`${new URL(request.url).protocol}//${host}`)return NextResponse.json({message:'请求来源无效。'},{status:403});
 try{
  const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+`/api/v1/works/${encodeURIComponent(workId)}/preferences`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify(await request.json()),signal:AbortSignal.timeout(10000)});
  const data=await r.json();return NextResponse.json(r.ok?data:{message:data.message||'标签格式不正确：最多 12 个，每个最多 30 字符。'},{status:r.status});
 }catch{return NextResponse.json({message:'无法保存作品管理设置，请刷新后重试。'},{status:503});}
}
