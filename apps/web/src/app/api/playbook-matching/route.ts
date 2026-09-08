import { NextResponse } from "next/server";
export async function GET(request:Request){
 const query=new URLSearchParams(),input=new URL(request.url).searchParams;
 for(const key of ['platform','content_type','direction','style'])query.set(key,input.get(key)||'');
 try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+'/api/v1/playbook-matching?'+query,{cache:'no-store',signal:AbortSignal.timeout(10000)});return NextResponse.json(await r.json(),{status:r.status});}
 catch{return NextResponse.json({message:'暂时无法读取 Skill 匹配结果。'},{status:503});}
}
