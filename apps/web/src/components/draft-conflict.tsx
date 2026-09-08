"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { DraftSnapshot } from "@/components/draft-history";

const fields = [
  ["title", "项目标题"], ["idea", "创作想法"], ["output_language", "输出语言"],
  ["platform", "目标平台"], ["content_type", "内容类型"], ["direction", "创作方向"],
  ["style", "表达风格"], ["playbook_id", "创作 Skill"],
] as const;
type Field = typeof fields[number][0];
const labels: Record<string, string> = {
  "zh-CN":"中文", en:"英文", "zh-en":"中英双语", tiktok:"TikTok", instagram:"Instagram", x:"X / Twitter", douyin:"抖音", xiaohongshu:"小红书",
  knowledge:"知识科普",technology:"AI / 技术解读",business:"商业 / 产品观察",commentary:"观点评论",story:"故事 / 案例",tutorial:"教程 / 操作指南",
  structure_borrowing:"结构借鉴",opinion_reverse:"观点反向",cross_domain:"跨领域迁移",deep_expand:"深度扩展",platform_adapt:"平台改写",
  professional:"理性专业",friendly:"朋友式讲解",sharp:"强观点犀利",storytelling:"故事化叙述",concise:"极简直接",auto:"自动匹配","structure-borrowing-v1":"结构借鉴，观点重构",
};
function flatten(snapshot: DraftSnapshot) {
  return { title:snapshot.title, idea:snapshot.idea||"", output_language:snapshot.output_language,
    platform:snapshot.brief?.platform||"tiktok",content_type:snapshot.brief?.content_type||"knowledge",direction:snapshot.brief?.direction||"structure_borrowing",style:snapshot.brief?.style||"professional",playbook_id:snapshot.brief?.playbook_id||"structure-borrowing-v1" };
}

export function DraftConflict({ local, latest, archived, onResolve }: { local:DraftSnapshot; latest:DraftSnapshot; archived:boolean; onResolve:(snapshot:DraftSnapshot)=>void }) {
  const [choices,setChoices]=useState<Partial<Record<Field,"local"|"latest">>>({});
  const [mergedBody,setMergedBody]=useState(local.body||"");
  const left=flatten(local),right=flatten(latest);
  function resolve(){
    const merged={...left};
    for(const [key] of fields) if(choices[key]==="latest")merged[key]=right[key];
    onResolve({title:merged.title,idea:merged.idea,output_language:merged.output_language,body:mergedBody,
      brief:{platform:merged.platform,content_type:merged.content_type,direction:merged.direction,style:merged.style,playbook_id:merged.playbook_id}});
  }
  return <section className="draft-conflict" aria-label="草稿版本对照">
    <h2>草稿版本对照</h2>
    <p>其他页面已保存新版本，或恢复的草稿基于旧版本。请选择要保留的内容；确认只会放回编辑器，不会自动保存。</p>
    {archived&&<p role="alert">最新项目已归档。可以先整理内容，恢复为草稿后再保存。</p>}
    {fields.filter(([key])=>left[key]!==right[key]).map(([key,label])=><div className="conflict-field" key={key}>
      <strong>{label}</strong>
      <div className="conflict-columns"><div><small>当前编辑</small><pre>{(key==='title'||key==='idea'?left[key]:labels[left[key]]||left[key])||'空'}</pre></div><div><small>最新保存</small><pre>{(key==='title'||key==='idea'?right[key]:labels[right[key]]||right[key])||'空'}</pre></div></div>
      <label>保留哪一版<select aria-label={`${label}采用版本`} value={choices[key]||'local'} onChange={e=>setChoices({...choices,[key]:e.target.value as 'local'|'latest'})}><option value="local">当前编辑</option><option value="latest">最新保存</option></select></label>
    </div>)}
    <div className="conflict-columns"><label>当前编辑正文<textarea readOnly aria-label="当前编辑正文" value={local.body||''}/></label><label>最新保存正文<textarea readOnly aria-label="最新保存正文" value={latest.body||''}/></label></div>
    <label>合并后的正文<textarea aria-label="合并后的正文" value={mergedBody} onChange={e=>setMergedBody(e.target.value)}/></label>
    <p>可从两侧复制所需段落，整理到合并后的正文；默认保留当前编辑。</p>
    <Button onClick={resolve}>确认对照，放回编辑器</Button>
  </section>;
}
