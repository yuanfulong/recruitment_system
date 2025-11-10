"""
LangGraph Agent 状态定义
定义所有工作流状态和数据结构
"""

from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime


class CandidateInfo(TypedDict):
    """候选人信息"""
    name: str
    age: Optional[int]
    email: Optional[str]
    phone: Optional[str]
    skills: List[Dict[str, Any]]
    work_experience: List[Dict[str, Any]]
    education: List[Dict[str, Any]]
    self_evaluation: Optional[str]
    extraction_quality: float


class JobIntention(TypedDict):
    """求职意向"""
    has_explicit_position: bool
    explicit_position: Optional[str]
    explicit_position_source: Optional[str]
    reasoning: str


class EvaluationScore(TypedDict):
    """评分结果"""
    position_id: int
    position_name: str
    overall_score: int
    grade: str  # A/B/C/D
    evaluation_reason: str
    matches: List[str]
    gaps: List[str]


class AllocationDecision(TypedDict):
    """分配决策"""
    auto_matched_position: str
    auto_matched_position_score: int
    is_position_locked: bool
    no_matched_position: bool


class ResumeProcessState(TypedDict):
    """
    简历处理工作流的状态
    这是LangGraph中最重要的数据结构，代表整个流程的上下文
    """

    # 输入数据
    pdf_content: str
    filename: str

    # Step 1-3: 信息提取阶段
    extracted_info: Optional[CandidateInfo]
    extraction_error: Optional[str]

    # Step 4: 求职意向分析
    job_intention: Optional[JobIntention]
    intention_error: Optional[str]

    # Step 5: 岗位评分
    evaluations: Dict[int, EvaluationScore]  # position_id -> score
    evaluation_errors: List[str]

    # Step 6: 分配决策
    allocation_decision: Optional[AllocationDecision]

    # Step 7: 数据库操作
    candidate_id: Optional[int]
    database_error: Optional[str]

    # 元数据
    status: str  # processing/success/error
    message: Optional[str]
    timestamp: str


class PositionAnalysisState(TypedDict):
    """
    岗位分析工作流的状态
    """

    # 输入数据
    position_name: str
    position_description: str

    # 分析结果
    required_skills: List[str]
    nice_to_have: List[str]
    evaluation_prompt: str
    analysis_error: Optional[str]

    # 创建结果
    position_id: Optional[int]
    creation_error: Optional[str]

    # 重新分配
    reallocation_changes: List[Dict[str, Any]]
    reallocation_error: Optional[str]

    # 元数据
    status: str  # analyzing/creating/reallocating/success/error
    message: Optional[str]


class ReallocationState(TypedDict):
    """
    重新分配工作流的状态
    """

    # 输入
    new_position_id: int
    new_position_name: str

    # 处理过程
    total_candidates: int
    processed_count: int
    updated_count: int

    # 结果
    changes: List[Dict[str, Any]]
    errors: List[str]

    # 元数据
    status: str  # processing/success/error
    message: Optional[str]


class QueryState(TypedDict):
    """
    自然语言查询工作流的状态
    """

    # 输入
    natural_language_query: str

    # 理解阶段
    query_type: str  # position_candidates/candidate_positions/statistics/etc
    query_params: Dict[str, Any]
    understanding_error: Optional[str]

    # 执行阶段
    query_results: List[Dict[str, Any]]
    total_count: int
    query_error: Optional[str]

    # 总结阶段
    summary: Optional[str]
    recommendation: Optional[str]
    summary_error: Optional[str]

    # 元数据
    status: str  # understanding/executing/summarizing/success/error
    message: Optional[str]


# 工作流事件定义
class WorkflowEvent:
    """工作流事件基类"""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.utcnow()

    def __repr__(self):
        return f"<WorkflowEvent {self.event_type} at {self.timestamp}>"


# 常用的状态更新函数
def create_resume_state(pdf_content: str, filename: str) -> ResumeProcessState:
    """创建初始的简历处理状态"""
    return {
        "pdf_content": pdf_content,
        "filename": filename,
        "extracted_info": None,
        "extraction_error": None,
        "job_intention": None,
        "intention_error": None,
        "evaluations": {},
        "evaluation_errors": [],
        "allocation_decision": None,
        "candidate_id": None,
        "database_error": None,
        "status": "processing",
        "message": "开始处理简历",
        "timestamp": datetime.utcnow().isoformat(),
    }


def create_position_state(name: str, description: str) -> PositionAnalysisState:
    """创建初始的岗位分析状态"""
    return {
        "position_name": name,
        "position_description": description,
        "required_skills": [],
        "nice_to_have": [],
        "evaluation_prompt": "",
        "analysis_error": None,
        "position_id": None,
        "creation_error": None,
        "reallocation_changes": [],
        "reallocation_error": None,
        "status": "analyzing",
        "message": "开始分析岗位",
    }


def create_query_state(query: str) -> QueryState:
    """创建初始的查询状态"""
    return {
        "natural_language_query": query,
        "query_type": "unknown",
        "query_params": {},
        "understanding_error": None,
        "query_results": [],
        "total_count": 0,
        "query_error": None,
        "summary": None,
        "recommendation": None,
        "summary_error": None,
        "status": "understanding",
        "message": "理解查询意图中",
    }