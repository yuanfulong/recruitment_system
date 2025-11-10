"""
Pydantic数据验证模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class SkillSchema(BaseModel):
    """技能模型"""
    skill: str
    level: str  # junior/intermediate/senior
    years: Optional[int] = None


class ExperienceSchema(BaseModel):
    """工作经历模型"""
    company: str
    position: str
    duration: str
    responsibilities: List[str]
    achievements: Optional[List[str]] = None


class EducationSchema(BaseModel):
    """教育背景模型"""
    school: str
    degree: str
    major: str
    graduation_date: Optional[str] = None


class CandidateExtractSchema(BaseModel):
    """简历提取的结构化信息"""
    name: str
    age: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    skills: List[SkillSchema] = []
    work_experience: List[ExperienceSchema] = []
    education: List[EducationSchema] = []
    certifications: Optional[List[str]] = None
    self_evaluation: Optional[str] = None
    
    extraction_quality: float = Field(0.0, ge=0, le=100)


class IntentionAnalysisSchema(BaseModel):
    """求职意向分析结果"""
    has_explicit_position: bool
    explicit_position: Optional[str] = None
    explicit_position_source: Optional[str] = None
    reasoning: str


class EvaluationResultSchema(BaseModel):
    """单个岗位的评分结果"""
    position_id: int
    position_name: str
    overall_score: int = Field(ge=0, le=100)
    grade: str = Field(pattern="^[A-D]$")
    evaluation_reason: str
    matches: List[str] = []
    gaps: List[str] = []
    potential: Optional[str] = None


class AllocationDecisionSchema(BaseModel):
    """分配决策"""
    candidate_id: int
    auto_matched_position: str
    auto_matched_position_score: int
    is_position_locked: bool
    no_matched_position: bool


class PositionCreateSchema(BaseModel):
    """创建岗位的请求"""
    name: str
    description: str
    required_skills: Optional[List[str]] = None
    nice_to_have: Optional[List[str]] = None


class PositionAnalysisSchema(BaseModel):
    """岗位分析结果"""
    position_id: int
    name: str
    base_score: int = 60
    required_skills: List[str]
    nice_to_have: List[str]
    evaluation_prompt: str


class ReallocationChangeSchema(BaseModel):
    """重新分配的一个变化记录"""
    candidate_id: int
    candidate_name: str
    reason: str
    old_position: Optional[str] = None
    old_score: Optional[int] = None
    new_position: str
    new_score: int
    score_improvement: Optional[int] = None


class BatchReallocationResultSchema(BaseModel):
    """批量重新分配的结果"""
    total_candidates_scanned: int
    candidates_reallocated: int
    changes: List[ReallocationChangeSchema]
    summary: Dict[str, Any]


class CandidateDetailSchema(BaseModel):
    """候选人详细信息（返回给前端）"""
    candidate_id: int
    name: str
    age: Optional[int] = None
    email: Optional[str] = None
    
    has_explicit_position: bool
    explicit_position: Optional[str] = None
    is_position_locked: bool
    no_matched_position: bool
    
    auto_matched_position: Optional[str] = None
    auto_matched_position_score: Optional[int] = None
    
    uploaded_at: datetime
    last_reallocation_at: Optional[datetime] = None
    reallocation_count: int


class MatchDetailSchema(BaseModel):
    """匹配详情"""
    position_name: str
    overall_score: int
    grade: str
    evaluation_reason: str
    is_qualified: bool


class CandidatePositionsSchema(BaseModel):
    """候选人在各岗位的表现"""
    candidate_id: int
    candidate_name: str
    positions: List[MatchDetailSchema]
    primary_position: str
    primary_score: int


class QueryRequestSchema(BaseModel):
    """自然语言查询请求"""
    query: str
    page: Optional[int] = 1
    page_size: Optional[int] = 20


class QueryResultSchema(BaseModel):
    """查询结果"""
    total: int
    page: int
    page_size: int
    results: List[Dict[str, Any]]
    summary: Optional[str] = None
    recommendation: Optional[str] = None


class ErrorResponseSchema(BaseModel):
    """错误响应"""
    status: str = "error"
    code: str
    message: str
    action: Optional[str] = None
    example: Optional[Dict[str, Any]] = None


class SuccessResponseSchema(BaseModel):
    """成功响应"""
    status: str = "success"
    data: Dict[str, Any]
    message: Optional[str] = None
