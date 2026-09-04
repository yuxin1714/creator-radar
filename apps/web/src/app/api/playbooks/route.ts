import { NextResponse } from "next/server";
const base = () => process.env.API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
export async function GET(){try{const r=await fetch(base()+"/api/v1/playbooks",{cache:"no-store"});return NextResponse.json(await r.json(),{status:r.status})}catch{return NextResponse.json({message:"暂时无法读取创作 Skill。"},{status:503})}}
export async function POST(request:Request){try{const r=await fetch(base()+"/api/v1/playbooks",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(await request.json())});return NextResponse.json(await r.json(),{status:r.status})}catch{return NextResponse.json({message:"API 暂时不可用。"},{status:503})}}
