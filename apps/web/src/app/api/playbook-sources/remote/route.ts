import { NextResponse } from "next/server";
export async function POST(request:Request){
 try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+'/api/v1/playbook-sources/remote',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(await request.json()),signal:AbortSignal.timeout(10000)});const d=await r.json();return NextResponse.json(r.ok?d:{message:d.message||'请检查名称、GitHub 仓库地址和 SKILL.md 相对路径。'},{status:r.status});}
 catch{return NextResponse.json({message:'暂时无法注册远程 Skill。'},{status:503});}
}
