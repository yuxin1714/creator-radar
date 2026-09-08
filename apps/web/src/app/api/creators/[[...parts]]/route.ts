import { NextResponse } from "next/server";
type Context={params:Promise<{parts?:string[]}>};
async function proxy(request:Request,context:Context){
 const {parts=[]}=await context.params;
 const valid=request.method==='GET'?parts.length<=1:request.method==='PATCH'?parts.length===1:parts.length===0||parts.length===2&&parts[1]==='check';
 if(!valid)return NextResponse.json({message:'接口不存在。'},{status:404});
 const origin=request.headers.get('origin'),host=request.headers.get('host')||new URL(request.url).host;
 if(request.method!=='GET'&&origin&&origin!==`${new URL(request.url).protocol}//${host}`)return NextResponse.json({message:'请求来源无效。'},{status:403});
 try{
  const body=request.method==='GET'?undefined:await request.text();
  const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+'/api/v1/creators'+(parts.length?'/'+parts.map(encodeURIComponent).join('/'):''),{method:request.method,body:body||undefined,headers:{'content-type':'application/json'},cache:'no-store',signal:AbortSignal.timeout(55000)});
  return NextResponse.json(await r.json(),{status:r.status});
 }catch{return NextResponse.json({message:'创作者服务暂时不可用，请刷新检查是否已添加。'},{status:503});}
}
export const GET=proxy;
export const POST=proxy;
export const PATCH=proxy;
