"use client";
import { Button } from "@/components/ui/button";
type Direction = {title:string;premise:string;hook:string;outline:string[]};
export function CreationDirections({content,disabled,onChoose}:{content:string;disabled:boolean;onChoose:(index:number)=>void}) {
  let directions:Direction[];
  try {
    const parsed=JSON.parse(content);
    if(!Array.isArray(parsed.directions)||parsed.directions.length!==3||!parsed.directions.every((d:Direction)=>typeof d.title==="string"&&typeof d.premise==="string"&&typeof d.hook==="string"&&Array.isArray(d.outline)&&d.outline.every(v=>typeof v==="string")))throw new Error();
    directions=parsed.directions;
  }catch{return <p role="alert">方向内容无法读取，请重新生成方向。</p>;}
  return <section className="generation-preview"><h2>选择创作方向</h2><p>选择后按生成这些方向时的平台、语言和 Skill 生成正文。修改配置后，请重新生成方向。</p>{directions.map((direction,index)=><article key={index} className="panel"><h3>{index+1}. {direction.title}</h3><p>{direction.premise}</p><p><strong>开场：</strong>{direction.hook}</p><ol>{direction.outline.map((line,i)=><li key={i}>{line}</li>)}</ol><Button disabled={disabled} onClick={()=>onChoose(index)}>选择方向 {index+1} 并生成正文</Button></article>)}</section>;
}
