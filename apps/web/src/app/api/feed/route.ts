import { NextResponse } from "next/server";
export async function GET(request:Request){
 const input=new URL(request.url).searchParams,params=new URLSearchParams();
 if(input.has('creator_id'))params.set('creator_id',input.get('creator_id')!);
 if(input.get('today')==='true')params.set('today','true');
 try{const r=await fetch((process.env.API_INTERNAL_BASE_URL??'http://127.0.0.1:8000')+'/api/v1/feed?'+params,{cache:'no-store',signal:AbortSignal.timeout(10000)});return NextResponse.json(await r.json(),{status:r.status});}
 catch{return NextResponse.json({message:'暂时无法读取情报。'},{status:503});}
}
