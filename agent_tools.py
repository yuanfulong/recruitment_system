"""
Agent工具定义 - 将现有系统功能包装为LangChain工具
不修改原有代码，通过工具包装实现Agent能力
"""

import logging
from typing import Optional, Dict, Any, List
from langchain.tools import tool
from pydantic import BaseModel, Field
from datetime import  datetime

# 导入现有系统组件
from service import RecruitmentService
from llm_service import LLMService
from models import Candidate, Position, CandidatePositionMatch
from pdf_processor import process_pdf_bytes
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ==================== 工具输入Schema定义 ====================

class UploadResumeInput(BaseModel):
    """上传简历工具的输入"""
    pdf_content: str = Field(description="PDF文件的文本内容")
    filename: str = Field(description="文件名")


class CreatePositionInput(BaseModel):
    """创建岗位工具的输入"""
    name: str = Field(description="岗位名称")
    description: str = Field(description="岗位描述")


class SearchCandidatesInput(BaseModel):
    """搜索候选人工具的输入"""
    position_name: Optional[str] = Field(None, description="岗位名称（可选）")
    min_score: Optional[int] = Field(None, description="最低分数（可选）")
    min_grade: Optional[str] = Field(None, description="最低等级：A/B/C/D（可选）")
    limit: int = Field(10, description="返回结果数量限制")


class GetCandidateDetailInput(BaseModel):
    """获取候选人详情工具的输入"""
    candidate_id: int = Field(description="候选人ID")


class GetPositionCandidatesInput(BaseModel):
    """获取岗位候选人工具的输入"""
    position_id: int = Field(description="岗位ID")
    min_grade: Optional[str] = Field(None, description="最低等级：A/B/C/D（可选）")


class EvaluateCandidateInput(BaseModel):
    """评估候选人工具的输入"""
    candidate_id: int = Field(description="候选人ID")
    position_id: int = Field(description="岗位ID")


class UpdateCandidatePositionInput(BaseModel):
    """更新候选人岗位分配的输入"""
    candidate_id: int = Field(description="候选人ID")
    new_position_id: int = Field(description="新岗位ID")
    reason: str = Field(description="更新原因")


class ListPositionsInput(BaseModel):
    """列出所有岗位的输入"""
    active_only: bool = Field(True, description="是否仅显示活跃岗位")


class GetPositionStatsInput(BaseModel):
    """获取岗位统计信息的输入"""
    position_id: int = Field(description="岗位ID")


# ==================== Agent工具类 ====================

class RecruitmentAgentTools:
    """招聘Agent工具集合 - 封装所有可用工具"""

    def __init__(self, session: Session, llm_service: LLMService, recruitment_service: RecruitmentService):
        """
        初始化Agent工具集

        Args:
            session: 数据库会话
            llm_service: LLM服务实例
            recruitment_service: 招聘服务实例
        """
        self.session = session
        self.llm = llm_service
        self.service = recruitment_service

    # ==================== 简历处理工具 ====================

    def create_upload_resume_tool(self):
        """创建上传简历工具"""

        @tool(args_schema=UploadResumeInput)
        def upload_resume(pdf_content: str, filename: str) -> str:
            """
            上传并处理简历PDF文件。

            这个工具会：
            1. 提取简历中的结构化信息（姓名、年龄、技能、工作经历等）
            2. 分析候选人的求职意向
            3. 对所有活跃岗位进行智能评分
            4. 自动分配最优岗位
            5. 保存到数据库

            返回：处理结果，包括候选人ID、分配的岗位、评分等信息
            """
            try:
                logger.info(f"🔧 [工具] 上传简历: {filename}")

                # 调用现有的简历处理服务
                result = self.service.process_resume(pdf_content, filename)

                # 格式化返回结果
                return f"""简历处理成功！
候选人ID: {result['candidate_id']}
姓名: {result['name']}
年龄: {result.get('age', '未提供')}
邮箱: {result.get('email', '未提供')}

分配结果：
- 分配岗位: {result['auto_matched_position']}
- 评分: {result['auto_matched_position_score']}/100
- 岗位状态: {'已锁定（候选人有明确意向）' if result['is_position_locked'] else '未锁定（可根据新岗位重新分配）'}
- 意向岗位{'不存在' if result.get('no_matched_position') else '已匹配'}

提取质量: {result.get('extraction_quality', 0)}/100
"""

            except Exception as e:
                logger.error(f"上传简历失败: {str(e)}")
                return f"错误：简历处理失败 - {str(e)}"

        return upload_resume

    # ==================== 岗位管理工具 ====================

    def create_position_tool(self):
        """创建岗位创建工具"""

        @tool(args_schema=CreatePositionInput)
        def create_position(name: str, description: str) -> str:
            """
            创建新的招聘岗位。

            这个工具会：
            1. 使用LLM分析岗位描述，提炼核心要求和加分项
            2. 生成详细的评分指南
            3. 保存岗位到数据库
            4. 自动触发所有候选人的重新分配评估

            返回：岗位创建结果和重新分配报告
            """
            try:
                logger.info(f"🔧 [工具] 创建岗位: {name}")

                # 调用现有的岗位创建服务
                result = self.service.create_position(name, description)

                # 格式化返回结果
                realloc = result['reallocation_result']
                return f"""岗位创建成功！
岗位ID: {result['position_id']}
岗位名称: {result['position_name']}

自动重新分配结果：
- 扫描候选人数: {realloc['total_candidates_scanned']}
- 重新分配数: {realloc['candidates_reallocated']}
- 变化详情: {len(realloc['changes'])}条

{self._format_reallocation_changes(realloc['changes'])}
"""

            except Exception as e:
                logger.error(f"创建岗位失败: {str(e)}")
                return f"错误：岗位创建失败 - {str(e)}"

        return create_position

    def create_list_positions_tool(self):
        """创建列出岗位工具"""

        @tool(args_schema=ListPositionsInput)
        def list_positions(active_only: bool = True) -> str:
            """
            列出所有招聘岗位及其统计信息。

            返回：岗位列表，包括岗位名称、ID、候选人数量、各等级分布等
            """
            try:
                logger.info(f"🔧 [工具] 列出岗位 (仅活跃: {active_only})")

                # 查询岗位
                query = self.session.query(Position)
                if active_only:
                    query = query.filter(Position.is_active == True)

                positions = query.all()

                if not positions:
                    return "当前系统中没有岗位。"

                # 格式化输出
                result = f"共找到 {len(positions)} 个岗位：\n\n"

                for pos in positions:
                    # 【修复】实时查询真实的候选人数量，而不是依赖统计字段
                    actual_total = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id
                    ).count()

                    actual_qualified = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id,
                        CandidatePositionMatch.is_qualified == True
                    ).count()

                    # 实时统计各等级人数
                    a_count = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id,
                        CandidatePositionMatch.grade == 'A'
                    ).count()

                    b_count = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id,
                        CandidatePositionMatch.grade == 'B'
                    ).count()

                    c_count = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id,
                        CandidatePositionMatch.grade == 'C'
                    ).count()

                    d_count = self.session.query(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == pos.position_id,
                        CandidatePositionMatch.grade == 'D'
                    ).count()

                    result += f"""📋 {pos.name} (ID: {pos.position_id})
   - 候选人总数: {actual_total} {'(实时查询)' if actual_total != pos.total_candidates else ''}
   - 合格人数: {actual_qualified}
   - 等级分布: A级{a_count}人, B级{b_count}人, C级{c_count}人, D级{d_count}人
   - 状态: {'活跃' if pos.is_active else '已关闭'}
   - 创建时间: {pos.created_at.strftime('%Y-%m-%d %H:%M')}

"""

                return result

            except Exception as e:
                logger.error(f"列出岗位失败: {str(e)}")
                return f"错误：列出岗位失败 - {str(e)}"

        return list_positions

    def create_get_position_stats_tool(self):
        """创建获取岗位统计工具"""

        @tool(args_schema=GetPositionStatsInput)
        def get_position_stats(position_id: int) -> str:
            """
            获取特定岗位的详细统计信息。

            返回：岗位的详细信息、候选人分布、评分统计等
            """
            try:
                logger.info(f"🔧 [工具] 获取岗位统计: {position_id}")

                position = self.session.query(Position).filter(
                    Position.position_id == position_id
                ).first()

                if not position:
                    return f"错误：未找到ID为 {position_id} 的岗位"

                # 获取该岗位的所有匹配记录
                matches = self.session.query(CandidatePositionMatch).filter(
                    CandidatePositionMatch.position_id == position_id
                ).all()

                # 【修复】实时计算统计信息
                actual_total = len(matches)
                actual_qualified = sum(1 for m in matches if m.is_qualified)

                # 计算各等级人数
                a_count = sum(1 for m in matches if m.grade == 'A')
                b_count = sum(1 for m in matches if m.grade == 'B')
                c_count = sum(1 for m in matches if m.grade == 'C')
                d_count = sum(1 for m in matches if m.grade == 'D')

                # 计算统计信息
                scores = [m.overall_score for m in matches]
                avg_score = sum(scores) / len(scores) if scores else 0

                result = f"""岗位详细统计：{position.name}
=================================
基本信息：
- 岗位ID: {position.position_id}
- 岗位描述: {position.description[:200]}...
- 基准分数: {position.base_score}
- 状态: {'活跃' if position.is_active else '已关闭'}

候选人统计（实时查询）：
- 总候选人数: {actual_total}
- 合格人数 (≥60分): {actual_qualified}
- 平均分数: {avg_score:.1f}

等级分布：
- A级 (90-100分): {a_count}人
- B级 (75-89分): {b_count}人
- C级 (60-74分): {c_count}人
- D级 (<60分): {d_count}人

核心要求：
{self._format_json_list(position.required_skills)}

加分项：
{self._format_json_list(position.nice_to_have)}
"""

                return result

            except Exception as e:
                logger.error(f"获取岗位统计失败: {str(e)}")
                return f"错误：获取岗位统计失败 - {str(e)}"

        return get_position_stats

    # ==================== 候选人查询工具 ====================

    def create_search_candidates_tool(self):
        """创建搜索候选人工具"""

        @tool(args_schema=SearchCandidatesInput)
        def search_candidates(
                position_name: Optional[str] = None,
                min_score: Optional[int] = None,
                min_grade: Optional[str] = None,
                limit: int = 10
        ) -> str:
            """
            搜索候选人，支持按岗位、分数、等级筛选。

            参数：
            - position_name: 岗位名称（可选）
            - min_score: 最低分数，0-100（可选）
            - min_grade: 最低等级，A/B/C/D（可选）
            - limit: 返回结果数量限制

            返回：符合条件的候选人列表
            """
            try:
                logger.info(
                    f"🔧 [工具] 搜索候选人: position={position_name}, min_score={min_score}, min_grade={min_grade}")

                # 构建查询
                query = self.session.query(Candidate)

                # 如果指定了岗位，需要join匹配表
                if position_name:
                    position = self.session.query(Position).filter(
                        Position.name == position_name
                    ).first()

                    if not position:
                        return f"错误：未找到名为 '{position_name}' 的岗位"

                    # Join匹配表进行过滤
                    query = query.join(CandidatePositionMatch).filter(
                        CandidatePositionMatch.position_id == position.position_id
                    )

                    # 分数过滤
                    if min_score is not None:
                        query = query.filter(CandidatePositionMatch.overall_score >= min_score)

                    # 等级过滤
                    if min_grade:
                        grade_order = {'A': 4, 'B': 3, 'C': 2, 'D': 1}
                        min_grade_value = grade_order.get(min_grade.upper(), 1)
                        valid_grades = [g for g, v in grade_order.items() if v >= min_grade_value]
                        query = query.filter(CandidatePositionMatch.grade.in_(valid_grades))

                    candidates = query.limit(limit).all()

                    # 格式化输出（带评分信息）
                    if not candidates:
                        return "未找到符合条件的候选人。"

                    result = f"找到 {len(candidates)} 个候选人（{position_name}岗位）：\n\n"

                    for candidate in candidates:
                        # 获取该候选人在此岗位的评分
                        match = self.session.query(CandidatePositionMatch).filter(
                            CandidatePositionMatch.candidate_id == candidate.candidate_id,
                            CandidatePositionMatch.position_id == position.position_id
                        ).first()

                        result += f"""👤 {candidate.name} (ID: {candidate.candidate_id})
   - 评分: {match.overall_score}/100 (等级: {match.grade})
   - 邮箱: {candidate.email or '未提供'}
   - 电话: {candidate.phone or '未提供'}
   - 评价: {match.evaluation_reason[:100]}...

"""

                else:
                    # 不指定岗位，返回所有候选人
                    candidates = query.limit(limit).all()

                    if not candidates:
                        return "系统中还没有候选人。"

                    result = f"找到 {len(candidates)} 个候选人：\n\n"

                    for candidate in candidates:
                        result += f"""👤 {candidate.name} (ID: {candidate.candidate_id})
   - 年龄: {candidate.age or '未提供'}
   - 邮箱: {candidate.email or '未提供'}
   - 当前分配: {candidate.auto_matched_position} ({candidate.auto_matched_position_score}分)
   - 意向状态: {'有明确意向' if candidate.has_explicit_position else '无明确意向'}
   - 上传时间: {candidate.uploaded_at.strftime('%Y-%m-%d %H:%M')}

"""

                return result

            except Exception as e:
                logger.error(f"搜索候选人失败: {str(e)}")
                return f"错误：搜索候选人失败 - {str(e)}"

        return search_candidates

    def create_get_candidate_detail_tool(self):
        """创建获取候选人详情工具"""

        @tool(args_schema=GetCandidateDetailInput)
        def get_candidate_detail(candidate_id: int) -> str:
            """
            获取候选人的完整详细信息。

            返回：候选人的基本信息、技能、工作经历、在各岗位的评分等
            """
            try:
                logger.info(f"🔧 [工具] 获取候选人详情: {candidate_id}")

                candidate = self.session.query(Candidate).filter(
                    Candidate.candidate_id == candidate_id
                ).first()

                if not candidate:
                    return f"错误：未找到ID为 {candidate_id} 的候选人"

                # 获取该候选人的所有岗位评分
                matches = self.session.query(CandidatePositionMatch).join(Position).filter(
                    CandidatePositionMatch.candidate_id == candidate_id
                ).all()

                # 格式化输出
                result = f"""候选人详细信息
=================================
基本信息：
- 姓名: {candidate.name}
- 年龄: {candidate.age or '未提供'}
- 邮箱: {candidate.email or '未提供'}
- 电话: {candidate.phone or '未提供'}

求职意向：
- 有明确意向: {'是' if candidate.has_explicit_position else '否'}
- 意向岗位: {candidate.explicit_position or '无'}
- 岗位状态: {'已锁定' if candidate.is_position_locked else '未锁定'}

当前分配：
- 分配岗位: {candidate.auto_matched_position}
- 评分: {candidate.auto_matched_position_score}/100

技能：
{self._format_json_list(candidate.skills_json)}

工作经历：
{candidate.work_experience or '无'}

教育背景：
{candidate.education or '无'}

自我评价：
{candidate.self_evaluation or '无'}

在各岗位的评分表现：
"""

                if not matches:
                    result += "（暂无岗位评分记录）"
                else:
                    for match in matches:
                        position = match.position
                        result += f"""
  📋 {position.name}
     - 评分: {match.overall_score}/100 (等级: {match.grade})
     - 是否合格: {'是' if match.is_qualified else '否'}
     - 评价: {match.evaluation_reason}
"""

                return result

            except Exception as e:
                logger.error(f"获取候选人详情失败: {str(e)}")
                return f"错误：获取候选人详情失败 - {str(e)}"

        return get_candidate_detail

    def create_get_position_candidates_tool(self):
        """创建获取岗位候选人工具"""

        @tool(args_schema=GetPositionCandidatesInput)
        def get_position_candidates(position_id: int, min_grade: Optional[str] = None) -> str:
            """
            获取某个岗位的所有候选人及其评分。

            返回：该岗位下所有候选人的详细信息和评分
            """
            try:
                logger.info(f"🔧 [工具] 获取岗位候选人: position_id={position_id}, min_grade={min_grade}")

                position = self.session.query(Position).filter(
                    Position.position_id == position_id
                ).first()

                if not position:
                    return f"错误：未找到ID为 {position_id} 的岗位"

                # 查询该岗位的所有匹配记录
                query = self.session.query(CandidatePositionMatch).join(Candidate).filter(
                    CandidatePositionMatch.position_id == position_id
                )

                # 等级过滤
                if min_grade:
                    grade_order = {'A': 4, 'B': 3, 'C': 2, 'D': 1}
                    min_grade_value = grade_order.get(min_grade.upper(), 1)
                    valid_grades = [g for g, v in grade_order.items() if v >= min_grade_value]
                    query = query.filter(CandidatePositionMatch.grade.in_(valid_grades))

                matches = query.order_by(CandidatePositionMatch.overall_score.desc()).all()

                if not matches:
                    return f"岗位 '{position.name}' 目前没有{'符合条件的' if min_grade else ''}候选人。"

                result = f"""岗位候选人列表：{position.name}
=================================
共 {len(matches)} 个候选人{f'（最低等级：{min_grade}）' if min_grade else ''}

"""

                for i, match in enumerate(matches, 1):
                    candidate = match.candidate
                    result += f"""{i}. {candidate.name} (ID: {candidate.candidate_id})
   - 评分: {match.overall_score}/100 (等级: {match.grade})
   - 邮箱: {candidate.email or '未提供'}
   - 电话: {candidate.phone or '未提供'}
   - 是否合格: {'✓ 是' if match.is_qualified else '✗ 否'}
   - 评价: {match.evaluation_reason[:150]}...
   - 评估时间: {match.evaluated_at.strftime('%Y-%m-%d %H:%M')}

"""

                return result

            except Exception as e:
                logger.error(f"获取岗位候选人失败: {str(e)}")
                return f"错误：获取岗位候选人失败 - {str(e)}"

        return get_position_candidates

    # ==================== 评估和更新工具 ====================

    def create_evaluate_candidate_tool(self):
        """创建重新评估候选人工具"""

        @tool(args_schema=EvaluateCandidateInput)
        def evaluate_candidate(candidate_id: int, position_id: int) -> str:
            """
            重新评估候选人对特定岗位的匹配度。

            这个工具会使用LLM重新分析候选人的简历，并对指定岗位进行评分。

            返回：新的评分结果
            """
            try:
                logger.info(f"🔧 [工具] 重新评估候选人: candidate_id={candidate_id}, position_id={position_id}")

                # 获取候选人和岗位
                candidate = self.session.query(Candidate).filter(
                    Candidate.candidate_id == candidate_id
                ).first()

                position = self.session.query(Position).filter(
                    Position.position_id == position_id
                ).first()

                if not candidate:
                    return f"错误：未找到ID为 {candidate_id} 的候选人"
                if not position:
                    return f"错误：未找到ID为 {position_id} 的岗位"

                # 准备候选人信息
                candidate_info = {
                    "name": candidate.name,
                    "age": candidate.age,
                    "skills": candidate.skills_json,
                    "work_experience": candidate.work_experience,
                    "education": candidate.education,
                    "self_evaluation": candidate.self_evaluation
                }

                # 调用LLM进行评估
                evaluation = self.llm.evaluate_candidate_for_position(
                    candidate_info=candidate_info,
                    position_name=position.name,
                    position_description=position.description,
                    evaluation_prompt=position.evaluation_prompt
                )

                # 更新数据库中的评分记录
                match = self.session.query(CandidatePositionMatch).filter(
                    CandidatePositionMatch.candidate_id == candidate_id,
                    CandidatePositionMatch.position_id == position_id
                ).first()

                if match:
                    # 更新现有记录
                    old_score = match.overall_score
                    match.overall_score = evaluation['overall_score']
                    match.grade = evaluation['grade']
                    match.evaluation_reason = evaluation['evaluation_reason']
                    match.evaluated_at = datetime.utcnow()
                    match.is_qualified = evaluation['overall_score'] >= 60

                    self.session.commit()

                    return f"""重新评估完成！

候选人: {candidate.name}
岗位: {position.name}

评分变化:
- 旧评分: {old_score}/100
- 新评分: {evaluation['overall_score']}/100 (等级: {evaluation['grade']})
- 变化: {evaluation['overall_score'] - old_score:+d}分

评价理由:
{evaluation['evaluation_reason']}

匹配点:
{self._format_list(evaluation.get('matches', []))}

不足之处:
{self._format_list(evaluation.get('gaps', []))}
"""
                else:
                    return f"警告：候选人 {candidate.name} 没有 {position.name} 岗位的评分记录"

            except Exception as e:
                logger.error(f"评估候选人失败: {str(e)}")
                return f"错误：评估候选人失败 - {str(e)}"

        return evaluate_candidate

    def create_update_candidate_position_tool(self):
        """创建更新候选人岗位分配工具"""

        @tool(args_schema=UpdateCandidatePositionInput)
        def update_candidate_position(candidate_id: int, new_position_id: int, reason: str) -> str:
            """
            手动更新候选人的岗位分配。

            这个工具允许HR手动调整候选人的岗位分配，系统会记录变更历史。

            返回：更新结果
            """
            try:
                logger.info(f"🔧 [工具] 更新候选人岗位: candidate_id={candidate_id}, new_position_id={new_position_id}")

                from models import PositionAllocationHistory, AuditLog

                # 获取候选人和新岗位
                candidate = self.session.query(Candidate).filter(
                    Candidate.candidate_id == candidate_id
                ).first()

                new_position = self.session.query(Position).filter(
                    Position.position_id == new_position_id
                ).first()

                if not candidate:
                    return f"错误：未找到ID为 {candidate_id} 的候选人"
                if not new_position:
                    return f"错误：未找到ID为 {new_position_id} 的岗位"

                # 获取新岗位的评分
                new_match = self.session.query(CandidatePositionMatch).filter(
                    CandidatePositionMatch.candidate_id == candidate_id,
                    CandidatePositionMatch.position_id == new_position_id
                ).first()

                if not new_match:
                    return f"错误：候选人 {candidate.name} 没有 {new_position.name} 岗位的评分记录，无法分配"

                # 记录变更
                old_position = candidate.auto_matched_position
                old_score = candidate.auto_matched_position_score

                # 更新候选人
                candidate.auto_matched_position = new_position.name
                candidate.auto_matched_position_score = new_match.overall_score
                candidate.last_reallocation_at = datetime.utcnow()
                candidate.reallocation_count += 1

                # 记录历史
                history = PositionAllocationHistory(
                    candidate_id=candidate_id,
                    old_position=old_position,
                    old_score=old_score,
                    new_position=new_position.name,
                    new_score=new_match.overall_score,
                    trigger_event="MANUAL",
                    reason=reason
                )
                self.session.add(history)

                # 审计日志
                audit = AuditLog(
                    operator="Agent",
                    action="UPDATE_CANDIDATE_POSITION",
                    candidate_id=candidate_id,
                    position_id=new_position_id,
                    details={
                        "old_position": old_position,
                        "new_position": new_position.name,
                        "reason": reason
                    }
                )
                self.session.add(audit)

                self.session.commit()

                return f"""岗位分配已更新！

候选人: {candidate.name} (ID: {candidate_id})

变更详情:
- 原岗位: {old_position} ({old_score}分)
- 新岗位: {new_position.name} ({new_match.overall_score}分)
- 变更原因: {reason}
- 评分变化: {new_match.overall_score - old_score:+d}分

新岗位评价:
{new_match.evaluation_reason}
"""

            except Exception as e:
                logger.error(f"更新候选人岗位失败: {str(e)}")
                self.session.rollback()
                return f"错误：更新候选人岗位失败 - {str(e)}"

        return update_candidate_position

    # ==================== 工具集合获取 ====================

    def get_all_tools(self) -> List:
        """
        获取所有可用的Agent工具

        Returns:
            工具列表，可直接传递给create_react_agent
        """
        tools = [
            # 简历处理
            self.create_upload_resume_tool(),

            # 岗位管理
            self.create_position_tool(),
            self.create_list_positions_tool(),
            self.create_get_position_stats_tool(),

            # 候选人查询
            self.create_search_candidates_tool(),
            self.create_get_candidate_detail_tool(),
            self.create_get_position_candidates_tool(),

            # 评估和更新
            self.create_evaluate_candidate_tool(),
            self.create_update_candidate_position_tool(),
        ]

        logger.info(f"✓ 已加载 {len(tools)} 个Agent工具")
        return tools

    # ==================== 辅助方法 ====================

    def _format_reallocation_changes(self, changes: List[Dict]) -> str:
        """格式化重新分配变化"""
        if not changes:
            return "（无变化）"

        result = ""
        for change in changes[:5]:  # 只显示前5条
            result += f"  - {change['candidate_name']}: {change['old_position']}({change.get('old_score', 0)}分) → {change['new_position']}({change['new_score']}分)\n"

        if len(changes) > 5:
            result += f"  ... 还有 {len(changes) - 5} 条变化\n"

        return result

    def _format_json_list(self, json_data) -> str:
        """格式化JSON列表"""
        if not json_data:
            return "（无）"

        if isinstance(json_data, list):
            return "\n".join([f"  - {item}" for item in json_data])
        elif isinstance(json_data, dict):
            return "\n".join([f"  - {k}: {v}" for k, v in json_data.items()])
        else:
            return str(json_data)

    def _format_list(self, items: List[str]) -> str:
        """格式化列表"""
        if not items:
            return "（无）"
        return "\n".join([f"  - {item}" for item in items])