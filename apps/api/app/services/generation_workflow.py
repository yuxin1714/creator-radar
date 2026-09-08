from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from app.models.work import CreationProject, CreationBrief, CreationGeneration, GenerationInput
from app.providers.base import ProviderError
from app.services.creation_playbooks import resolve_playbook


class GenerationOptions(BaseModel):
    mode: Literal["draft", "directions", "refine"] = "draft"
    feedback: str | None = Field(default=None, max_length=5000)
    direction_generation_id: str | None = Field(default=None, max_length=36)
    direction_index: int | None = Field(default=None, ge=0, le=2)


class Direction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    premise: str = Field(min_length=1, max_length=1500)
    hook: str = Field(min_length=1, max_length=1000)
    outline: list[str] = Field(min_length=2, max_length=8)


class DirectionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    directions: list[Direction] = Field(min_length=3, max_length=3)


def prepare_generation(db, project_id, options, settings):
    from app.services.creation_generation import reference_context
    project = db.scalar(select(CreationProject).where(CreationProject.id == project_id, CreationProject.owner_id == "local-user").with_for_update())
    if not project:
        raise ProviderError("project_not_found", "创作项目不存在。")
    brief = db.get(CreationBrief, project_id)
    if not brief:
        raise ProviderError("brief_required", "请先保存创作选项。")
    active = db.scalar(select(CreationGeneration.id).where(CreationGeneration.project_id == project_id, CreationGeneration.status.in_(["PENDING", "PROCESSING"])))
    if active:
        raise ProviderError("generation_running", "这个项目已有生成任务，请等待完成。")
    if options.mode == "refine" and (not (options.feedback or "").strip() or not (project.body or "").strip()):
        raise ProviderError("refinement_required", "请先填写正文和修改意见。")
    if options.mode != "refine" and options.feedback is not None:
        raise ProviderError("invalid_feedback", "修改意见仅用于反馈优化任务。")
    if options.direction_generation_id is not None or options.direction_index is not None:
        if options.mode != "draft" or options.direction_generation_id is None or options.direction_index is None:
            raise ProviderError("invalid_direction", "请选择完整的创作方向。")
        source = db.scalar(select(CreationGeneration).where(CreationGeneration.id == options.direction_generation_id, CreationGeneration.project_id == project_id, CreationGeneration.status == "COMPLETED"))
        source_input = db.get(GenerationInput, source.id) if source else None
        if not source_input or source_input.mode != "directions":
            raise ProviderError("invalid_direction", "方向不属于当前项目或尚未生成完成。")
        try:
            chosen = DirectionSet.model_validate_json(source.content).directions[options.direction_index]
        except Exception as error:
            raise ProviderError("invalid_direction", "方向内容无效，请重新生成方向。") from error
        # Preserve the brief and Skill that produced the chosen direction.
        context = dict(source_input.context)
        context["selected_direction"] = chosen.model_dump()
        context["direction_generation_id"] = source.id
        context["existing_draft"] = project.body or ""
        revision = source.playbook_revision
        skill_id = source.playbook_id
    else:
        skill_id = brief.playbook_id
        revision, skill = resolve_playbook(db, skill_id)
        reference = reference_context(db, project)
        context = {"output_language": project.output_language, "platform": brief.platform, "content_type": brief.content_type,
                   "direction": brief.direction, "style": brief.style, "title": project.title, "idea": project.idea or "",
                   "existing_draft": project.body or "", "skill": skill, "reference": reference}
    if options.mode == "refine":
        context["feedback"] = options.feedback.strip()
    generation = CreationGeneration(project_id=project_id, playbook_id=skill_id, playbook_revision=revision)
    db.add(generation); db.flush()
    db.add(GenerationInput(generation_id=generation.id, mode=options.mode, context=context, model=settings.llm_model))
    db.flush()
    return generation
