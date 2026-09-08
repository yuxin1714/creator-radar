"use client";
import { DraftPreview } from "@/components/draft-preview";
import Link from "next/link";
import { MatchingPreview } from "@/components/playbook-matching";
import { GenerationHistory } from "@/components/generation-history";
import { CreationDirections } from "@/components/creation-directions";
import { readRecovery, recoveryKey } from "@/lib/draft-recovery";
import { useUnsavedDraft } from "@/hooks/use-unsaved-draft";
import { DraftHistory, type DraftSnapshot } from "@/components/draft-history";
import { ExportDraft } from "@/components/export-draft";
import { useEffect, useState } from "react";
import { ArrowLeft, Check, LoaderCircle, Save, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
type Brief={platform:string;content_type:string;direction:string;style:string;playbook_id:string};type Generation={mode?:"draft"|"directions"|"refine";id:string;status:string;content:string|null;error_summary:string|null;playbook_id:string;playbook_revision:string|null};type Project={work_id:string|null;output_language:string;id:string;title:string;idea:string|null;status:string;body:string|null;updated_at:string;brief:Brief|null;latest_generation:Generation|null};type Playbook={id:string;name:string;revision:string|null};
const platforms=[['tiktok','TikTok'],['instagram','Instagram'],['x','X / Twitter'],['douyin','抖音'],['xiaohongshu','小红书']];const contentTypes=[['knowledge','知识科普'],['technology','AI / 技术解读'],['business','商业 / 产品观察'],['commentary','观点评论'],['story','故事 / 案例'],['tutorial','教程 / 操作指南']];const directions=[['structure_borrowing','结构借鉴'],['opinion_reverse','观点反向'],['cross_domain','跨领域迁移'],['deep_expand','深度扩展'],['platform_adapt','平台改写']];const styles=[['professional','理性专业'],['friendly','朋友式讲解'],['sharp','强观点犀利'],['storytelling','故事化叙述'],['concise','极简直接']];
export function CreationDetail({projectId}:{projectId:string}){const [item,setItem]=useState<Project|null>(null),[skills,setSkills]=useState<Playbook[]>([]),[title,setTitle]=useState(""),[idea,setIdea]=useState(""),[body,setBody]=useState(""),[brief,setBrief]=useState<Brief>({platform:"tiktok",content_type:"knowledge",direction:"structure_borrowing",style:"professional",playbook_id:"structure-borrowing-v1"}),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[generating,setGenerating]=useState(false);
 const [feedback,setFeedback]=useState("");
 const [pollEpoch,setPollEpoch]=useState(0);
 const [recovery,setRecovery]=useState<DraftSnapshot|null>(null);
 const [recoveryError,setRecoveryError]=useState("");
 const [historyRefresh,setHistoryRefresh]=useState(0);
 function loadVersion(snapshot:DraftSnapshot){
   setTitle(snapshot.title);setIdea(snapshot.idea||"");setBody(snapshot.body||"");setLanguage(snapshot.output_language);
   if(snapshot.brief)setBrief(snapshot.brief);
   setMessage("历史版本已载入编辑器，保存后生效。");
 }
 const [language,setLanguage]=useState("zh-CN");
 const defaultBrief:Brief={platform:"tiktok",content_type:"knowledge",direction:"structure_borrowing",style:"professional",playbook_id:"structure-borrowing-v1"};
 const savedBrief=item?.brief||defaultBrief;
 const dirty=!!item&&(title!==item.title||idea!==(item.idea||"")||body!==(item.body||"")||language!==item.output_language||(Object.keys(defaultBrief) as Array<keyof Brief>).some(key=>brief[key]!==savedBrief[key]));
 useUnsavedDraft(dirty);
 useEffect(()=>{
   if(!item||item.id!==projectId||recovery)return;
   try{
     if(dirty)sessionStorage.setItem(recoveryKey(projectId),JSON.stringify({title,idea,body,output_language:language,brief}));
     else sessionStorage.removeItem(recoveryKey(projectId));
     setRecoveryError("");
   }catch{setRecoveryError("浏览器暂存不可用，请及时保存草稿。");}
 },[projectId,item,dirty,recovery,title,idea,body,language,brief]);
 function recoverDraft(){
   if(!recovery)return;
   loadVersion(recovery);setRecovery(null);
   setMessage("未保存草稿已恢复，保存后写入项目。");
 }
 function discardRecovery(){
   try{sessionStorage.removeItem(recoveryKey(projectId));setRecovery(null);}
   catch{setRecoveryError("无法清除浏览器暂存。");}
 }
 useEffect(()=>{
   const controller=new AbortController();
   setItem(null);setRecovery(null);
   async function load(){
     try {
       const r=await fetch(`/api/creation-projects/${encodeURIComponent(projectId)}`,{cache:"no-store",signal:controller.signal});
       const project=await r.json();
       if(!r.ok)throw new Error(project.message||"无法读取项目");
       if(controller.signal.aborted)return;
       setItem(project);setTitle(project.title);setIdea(project.idea||"");setBody(project.body||"");setLanguage(project.output_language||"zh-CN");
       setBrief(project.brief||defaultBrief);
       try{
         const cached=readRecovery(projectId);
         const baseline={title:project.title,idea:project.idea||"",body:project.body||"",output_language:project.output_language,brief:project.brief||defaultBrief};
         if(cached&&JSON.stringify(cached)!==JSON.stringify(baseline))setRecovery(cached);
       }catch{setRecoveryError("浏览器暂存不可用，请及时保存草稿。");}
       const sr=await fetch("/api/playbooks",{cache:"no-store",signal:controller.signal});
       if(!sr.ok)throw new Error("Skill 列表读取失败");
       const skills=await sr.json();
       if(!controller.signal.aborted&&Array.isArray(skills))setSkills(skills);
     }catch(e){if(!controller.signal.aborted)setMessage(e instanceof Error?e.message:"读取失败");}
   }
   void load();
   return ()=>controller.abort();
 },[projectId]);
 const pending=item?.latest_generation?.status==="PENDING"||item?.latest_generation?.status==="PROCESSING";
 useEffect(()=>{
   if(!pending)return;
   const controller=new AbortController();
   let timer:ReturnType<typeof setTimeout>;
   async function poll(){
     try{
       const r=await fetch(`/api/creation-projects/${encodeURIComponent(projectId)}`,{cache:"no-store",signal:controller.signal});
       const project=await r.json();
       if(!r.ok)throw new Error(project.message||"状态读取失败");
       if(controller.signal.aborted)return;
       // Poll only the generation: never replace unsaved editor fields.
       setItem(current=>current?{...current,latest_generation:project.latest_generation}:current);
       if(["PENDING","PROCESSING"].includes(project.latest_generation?.status))timer=setTimeout(poll,3000);
     }catch(e){
       if(!controller.signal.aborted){
         setMessage("状态刷新失败，正在重试。");
         timer=setTimeout(poll,3000);
       }
     }
   }
   timer=setTimeout(poll,1000);
   return ()=>{controller.abort();clearTimeout(timer);};
 },[projectId,pending,pollEpoch]);
 async function save():Promise<boolean>{
   setBusy(true);setMessage("");
   try{
     const r=await fetch(`/api/creation-projects/${encodeURIComponent(projectId)}`,{method:"PATCH",headers:{"content-type":"application/json"},body:JSON.stringify({title,idea:idea||null,body:body||null,output_language:language,...brief,expected_updated_at:item?.updated_at})});
     const d=await r.json();
     if(!r.ok)throw new Error(d.message||"保存失败");
     setItem(d);setRecovery(null);setHistoryRefresh(x=>x+1);setMessage("草稿和创作 Skill 已保存。");
     return true;
   }catch(e){setMessage(e instanceof Error?e.message:"保存失败。");return false;}
   finally{setBusy(false);}
 }
 async function generate(options:{mode:"draft"|"directions"|"refine";direction_generation_id?:string;direction_index?:number;feedback?:string}={mode:"draft"}){
   setGenerating(true);setMessage("");
   try{
     if(!await save())return;
     const r=await fetch(`/api/creation-projects/${encodeURIComponent(projectId)}/generations`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(options)});
     const d=await r.json();
     if(!r.ok)throw new Error(d.message||"无法开始生成");
     setItem(current=>current?{...current,latest_generation:{mode:options.mode,id:d.generation_id,status:"PENDING",content:null,error_summary:null,playbook_id:brief.playbook_id,playbook_revision:null}}:current);
     setPollEpoch(x=>x+1);
     setMessage(options.mode==="directions"?"正在按所选 Skill 生成三个方向。":options.mode==="refine"?"正在根据修改意见优化正文。":"正在按所选 Skill 生成草稿。");
   }catch(e){setMessage(e instanceof Error?e.message:"无法开始生成。");}
   finally{setGenerating(false);}
 }
 if(!item&&!message)return <div className="detail-loading"><LoaderCircle className="spin"/>正在读取创作项目…</div>;if(!item)return <><Link className="back-link" href="/creation"><ArrowLeft size={15}/>返回创作空间</Link><section className="panel detail-error"><h1>无法打开项目</h1><p>{message}</p></section></>;const select=(label:string,key:keyof Brief,options:string[][])=><label>{label}<select value={brief[key]} onChange={e=>setBrief({...brief,[key]:e.target.value})}>{options.map(([value,text])=><option key={value} value={value}>{text}</option>)}</select></label>;const generation=item.latest_generation,running=generation?.status==="PENDING"||generation?.status==="PROCESSING";return <><Link className="back-link" href="/creation"><ArrowLeft size={15}/>返回创作空间</Link><section className="panel creation-editor">{recovery&&<div className="draft-recovery" role="status"><p>发现此项目的未保存草稿</p><Button variant="outline" onClick={recoverDraft}>恢复未保存草稿</Button><Button variant="ghost" onClick={discardRecovery}>丢弃暂存</Button></div>}{recoveryError&&<p role="alert" className="draft-recovery">{recoveryError}</p>}<div className="section-heading"><div><p className="eyebrow">CREATION DRAFT</p><h1>{item.title}</h1><p>草稿项目 · {item.status} · <span role="status">{busy?"正在保存":dirty?"未保存":"已保存"}</span></p></div><span className="neutral-label">{new Date(item.updated_at).toLocaleDateString("zh-CN")}</span></div>{item.work_id&&<div className="creation-reference"><span>参考作品已关联</span><Link href={`/works/${item.work_id}?tab=analysis`}>查看作品与分析</Link></div>}<label>项目标题<input value={title} onChange={e=>setTitle(e.target.value)}/></label><label>创作想法<textarea value={idea} onChange={e=>setIdea(e.target.value)} placeholder="记录主题、受众或想表达的观点"/></label><div className="brief-grid"><label>输出语言<select aria-label="输出语言" value={language} onChange={e=>setLanguage(e.target.value)}><option value="zh-CN">中文</option><option value="en">English</option><option value="zh-en">中英双语</option></select></label>{select("目标平台","platform",platforms)}{select("内容类型","content_type",contentTypes)}{select("创作方向","direction",directions)}{select("表达风格","style",styles)}<label>创作 Skill<select value={brief.playbook_id} onChange={e=>setBrief({...brief,playbook_id:e.target.value})}>{brief.playbook_id!=="auto"&&brief.playbook_id!=="structure-borrowing-v1"&&!skills.some(skill=>skill.id===brief.playbook_id)&&<option value={brief.playbook_id} disabled>已停用或不可用：{brief.playbook_id}</option>}<option value="auto">自动匹配（按创作配置）</option><option value="structure-borrowing-v1">结构借鉴，观点重构</option>{skills.map(skill=><option key={skill.id} value={skill.id}>{skill.name}{skill.revision?` · ${skill.revision.slice(0,8)}`:""}</option>)}</select></label></div>{brief.playbook_id==="auto"&&<MatchingPreview platform={brief.platform} contentType={brief.content_type} direction={brief.direction} style={brief.style}/>}<label>正文草稿<textarea className="body-editor" value={body} onChange={e=>setBody(e.target.value)} placeholder="在这里编辑正文；生成结果需先采用，再保存到草稿"/></label><div className="editor-actions"><ExportDraft title={title} body={body} workId={item.work_id}/><Button onClick={save} disabled={busy||generating||!title.trim()}>{busy?<LoaderCircle className="spin" size={15}/>:<Save size={15}/>}保存草稿</Button><Button variant="outline" onClick={()=>void generate()} disabled={busy||generating||running||!title.trim()}>{generating||running?<LoaderCircle className="spin" size={15}/>:<Sparkles size={15}/>}生成草稿</Button><Button variant="outline" onClick={()=>void generate({mode:"directions"})} disabled={busy||generating||running||!title.trim()}>生成三个创作方向</Button>{message&&<span><Check size={15}/>{message}</span>}</div>{running&&<div className="generation-progress"><LoaderCircle className="spin" size={17}/>正在按已选择的 Skill 生成内容…</div>}{generation?.status==="FAILED"&&<p className="task-error">{generation.error_summary}</p>}{generation?.status==="COMPLETED"&&generation.content&&(generation.mode==="directions"?<CreationDirections content={generation.content} disabled={busy||generating||!!running} onChoose={index=>void generate({mode:"draft",direction_generation_id:generation.id,direction_index:index})}/>:<section className="generation-preview"><div><strong>生成预览</strong><small>Skill {generation.playbook_id} · {generation.playbook_revision?.slice(0,8)||"本地版本"}</small></div><DraftPreview content={generation.content}/><Button onClick={()=>setBody(generation.content||"")}>采用到正文</Button></section>)}<section className="generation-preview"><h2>反馈优化</h2><p>以编辑器当前正文为基础，按所选 Skill 和修改意见生成修订稿，原稿不会自动替换。</p><label>修改意见<textarea value={feedback} maxLength={5000} onChange={e=>setFeedback(e.target.value)} placeholder="例如：开场更直接，保留结尾反转，减少产品介绍"/></label><Button variant="outline" disabled={busy||generating||!!running||!body.trim()||!feedback.trim()||!title.trim()} onClick={()=>void generate({mode:"refine",feedback})}>按反馈优化正文</Button></section><GenerationHistory projectId={projectId} refresh={`${generation?.id}:${generation?.status}`} disabled={busy||generating||!!running} onAdopt={setBody} onChoose={(id,index)=>void generate({mode:"draft",direction_generation_id:id,direction_index:index})}/><DraftHistory projectId={projectId} refresh={historyRefresh} onLoad={loadVersion}/><div className="quiet-note">生成结果先保留为预览，只有点击“采用到正文”后才会替换编辑器中的内容。</div></section></>}
