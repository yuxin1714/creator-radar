from pydantic import BaseModel, Field, ConfigDict


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = Field(min_length=1, max_length=2000)
    quote: str = Field(min_length=1, max_length=2000)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=10000)
    hook: str = Field(min_length=1, max_length=5000)
    structure: list[str] = Field(min_length=1, max_length=30)
    key_points: list[str] = Field(min_length=1, max_length=30)
    content_score: int = Field(ge=0, le=100, strict=True)
    score_reasons: list[str] = Field(min_length=1, max_length=30)
    evidence: list[Evidence] = Field(min_length=1, max_length=30)


def validate_analysis(result, transcript):
    parsed = AnalysisResult.model_validate(result)
    for evidence in parsed.evidence:
        quote = evidence.quote.strip()
        if not quote or quote not in transcript:
            raise ValueError("分析证据未出现在逐字稿中")
    return parsed.model_dump()
