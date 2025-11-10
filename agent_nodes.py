"""
LangGraph Agent 工作流节点
实现所有的工作流处理逻辑
"""

import logging
from typing import Dict, Any
from datetime import datetime
from agent_state import (
    ResumeProcessState, PositionAnalysisState, QueryState,
    create_resume_state, create_position_state, create_query_state,
    AllocationDecision, EvaluationScore
)
from llm_service import LLMService
from service import RecruitmentService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RecruitmentAgent:
    """招聘Agent - 封装所有工作流节点"""

    def __init__(self, session: Session, llm_service: LLMService, service: RecruitmentService):
        self.session = session
        self.llm = llm_service
        self.service = service


# ==================== 简历处理工作流节点 ====================

class ResumeProcessingNodes:
    """简历处理工作流的所有节点"""

    def __init__(self, llm_service: LLMService, service: RecruitmentService, session: Session = None):
        self.llm = llm_service
        self.service = service
        self.session = session

    def node_extract_info(self, state: ResumeProcessState) -> ResumeProcessState:
        """
        节点：提取候选人信息

        输入：pdf_content
        输出：extracted_info 或 extraction_error
        """
        logger.info("🔄 [节点] 提取候选人信息...")

        try:
            candidate_info = self.llm.extract_candidate_info(state["pdf_content"])

            state["extracted_info"] = candidate_info
            state["extraction_error"] = None
            state["message"] = "✓ 信息提取成功"
            logger.info(f"✓ 提取候选人: {candidate_info.get('name')}")

        except Exception as e:
            logger.error(f"✗ 提取失败: {str(e)}")
            state["extraction_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"信息提取失败: {str(e)}"

        return state

    def node_analyze_intention(self, state: ResumeProcessState) -> ResumeProcessState:
        """
        节点：分析求职意向

        输入：extracted_info
        输出：job_intention 或 intention_error
        """
        logger.info("🔄 [节点] 分析求职意向...")

        # 短路：如果提取失败，跳过此节点
        if state["extraction_error"]:
            logger.warning("⏭️ 跳过：提取失败")
            state["status"] = "error"
            return state

        try:
            intention = self.llm.analyze_job_intention(state["extracted_info"])

            state["job_intention"] = intention
            state["intention_error"] = None
            state["message"] = "✓ 求职意向分析完成"

            if intention.get("has_explicit_position"):
                logger.info(f"✓ 发现明确意向: {intention.get('explicit_position')}")
            else:
                logger.info("✓ 无明确意向，将自动分配")

        except Exception as e:
            logger.error(f"✗ 分析失败: {str(e)}")
            state["intention_error"] = str(e)
            # 降级处理：设置默认无意向
            state["job_intention"] = {
                "has_explicit_position": False,
                "explicit_position": None,
                "explicit_position_source": None,
                "reasoning": f"分析失败，默认无意向: {str(e)}"
            }

        return state

    def node_evaluate_positions(self, state: ResumeProcessState) -> ResumeProcessState:
        """
        节点：对所有岗位评分

        输入：extracted_info
        输出：evaluations
        """
        logger.info("🔄 [节点] 对所有岗位评分...")

        if state["extraction_error"]:
            logger.warning("⏭️ 跳过：提取失败")
            state["status"] = "error"
            return state

        # 获取所有活跃岗位
        from models import Position

        if self.session:
            positions = self.session.query(Position).filter(Position.is_active == True).all()
        else:
            positions = []

        if not positions:
            logger.warning("⚠️ 没有活跃岗位")
            state["evaluation_errors"].append("没有活跃岗位")
            state["status"] = "error"
            state["message"] = "没有活跃岗位"
            return state

        logger.info(f"📋 评分 {len(positions)} 个岗位...")

        for position in positions:
            try:
                eval_result = self.llm.evaluate_candidate_for_position(
                    state["extracted_info"],
                    position.name,
                    position.description,
                    position.required_skills or []
                )

                state["evaluations"][position.position_id] = eval_result
                logger.info(f"  ✓ {position.name}: {eval_result.get('overall_score')}分 ({eval_result.get('grade')}级)")

            except Exception as e:
                logger.warning(f"  ✗ {position.name} 评分失败: {str(e)}")
                state["evaluation_errors"].append(f"{position.name}: {str(e)}")
                # 降级处理：给默认低分
                state["evaluations"][position.position_id] = {
                    "overall_score": 0,
                    "grade": "D",
                    "evaluation_reason": f"评分失败: {str(e)}",
                    "matches": [],
                    "gaps": [],
                }

        if not state["evaluations"]:
            state["status"] = "error"
            state["message"] = "所有岗位评分失败"
            return state

        state["message"] = f"✓ 完成 {len(state['evaluations'])} 个岗位评分"
        return state

    def node_make_allocation_decision(self, state: ResumeProcessState) -> ResumeProcessState:
        """
        节点：做出分配决策

        三层逻辑：
        1. 有意向 + 岗位存在 → 锁定
        2. 有意向 + 岗位不存在 → 标记 no_matched
        3. 无意向 → 分配最优

        输入：job_intention, evaluations
        输出：allocation_decision
        """
        logger.info("🔄 [节点] 做出分配决策...")

        if not state["evaluations"]:
            logger.error("✗ 无评分数据")
            state["status"] = "error"
            state["message"] = "无评分数据，无法分配"
            return state

        # 找最优岗位
        best_position_id = None
        best_score = -1

        for pos_id, eval_result in state["evaluations"].items():
            score = eval_result.get("overall_score", 0)
            if score > best_score:
                best_score = score
                best_position_id = pos_id

        # 获取最优岗位名称
        if best_position_id and self.session:
            from models import Position
            best_position = self.session.query(Position).filter(
                Position.position_id == best_position_id
            ).first()
            best_position_name = best_position.name if best_position else "未知岗位"
        else:
            best_position_name = None

        intention = state["job_intention"]
        is_locked = False
        no_matched = False

        # 情况1：有明确意向
        if intention and intention.get("has_explicit_position"):
            if self.session:
                from models import Position
                explicit_pos = self.session.query(Position).filter(
                    Position.name == intention.get("explicit_position")
                ).first()

                if explicit_pos:
                    # 情况1a：意向岗位存在 → 锁定该岗位
                    logger.info(f"📌 情况1a：意向岗位'{intention.get('explicit_position')}'存在，锁定")
                    is_locked = True
                    best_position_name = explicit_pos.name
                    best_position_id = explicit_pos.position_id
                    best_score = state["evaluations"].get(explicit_pos.position_id, {}).get("overall_score", 60)
                else:
                    # 情况1b：意向岗位不存在 → 临时分配最优，标记等待
                    logger.info(f"📌 情况1b：意向岗位'{intention.get('explicit_position')}'不存在，临时分配最优，等待")
                    is_locked = False
                    no_matched = True
        else:
            # 情况3：无明确意向 → 分配最优，可重新分配
            logger.info(f"📌 情况3：无明确意向，分配最优岗位")
            is_locked = False
            no_matched = False

        state["allocation_decision"] = {
            "auto_matched_position": best_position_name,
            "auto_matched_position_score": best_score,
            "is_position_locked": is_locked,
            "no_matched_position": no_matched
        }

        state["message"] = f"✓ 分配决策完成: {best_position_name} ({best_score}分)"
        logger.info(f"✓ 分配决策: {best_position_name} (锁定={is_locked}, 待匹配={no_matched})")

        return state

    def node_save_to_database(self, state: ResumeProcessState) -> ResumeProcessState:
        """
        节点：保存到数据库

        输入：extracted_info, job_intention, allocation_decision
        输出：candidate_id 或 database_error
        """
        logger.info("🔄 [节点] 保存到数据库...")

        if state["extraction_error"]:
            logger.warning("⏭️ 跳过：提取失败")
            state["status"] = "error"
            return state

        try:
            # 调用原有的保存逻辑
            result = self.service.process_resume_save(
                candidate_info=state["extracted_info"],
                job_intention=state["job_intention"],
                evaluations=state["evaluations"],
                allocation_decision=state["allocation_decision"],
                filename=state["filename"]
            )

            state["candidate_id"] = result.get("candidate_id")
            state["database_error"] = None
            state["status"] = "success"
            state["message"] = f"✓ 候选人保存成功 (ID: {result.get('candidate_id')})"

            logger.info(f"✓ 候选人已保存到数据库 (ID: {result.get('candidate_id')})")

        except Exception as e:
            logger.error(f"✗ 保存失败: {str(e)}", exc_info=True)
            state["database_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"保存失败: {str(e)}"

        return state


# ==================== 岗位分析工作流节点 ====================

class PositionAnalysisNodes:
    """岗位分析工作流的所有节点"""

    def __init__(self, llm_service: LLMService, service: RecruitmentService, session: Session = None):
        self.llm = llm_service
        self.service = service
        self.session = session

    def node_analyze_position(self, state: PositionAnalysisState) -> PositionAnalysisState:
        """节点：分析岗位要求"""
        logger.info(f"🔄 [节点] 分析岗位: {state['position_name']}")

        try:
            analysis = self.llm.analyze_position(
                state["position_name"],
                state["position_description"]
            )

            state["required_skills"] = analysis.get("required_skills", [])
            state["nice_to_have"] = analysis.get("nice_to_have", [])
            state["evaluation_prompt"] = analysis.get("evaluation_prompt", "")
            state["analysis_error"] = None
            state["message"] = "✓ 岗位分析完成"

            logger.info(f"✓ 岗位分析完成: {len(state['required_skills'])} 项必需技能")

        except Exception as e:
            logger.error(f"✗ 分析失败: {str(e)}")
            state["analysis_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"分析失败: {str(e)}"

        return state

    def node_create_position(self, state: PositionAnalysisState) -> PositionAnalysisState:
        """节点：创建岗位"""
        logger.info("🔄 [节点] 创建岗位...")

        if state["analysis_error"]:
            logger.warning("⏭️ 跳过：分析失败")
            state["status"] = "error"
            return state

        try:
            from models import Position
            position = Position(
                name=state["position_name"],
                description=state["position_description"],
                base_score=60,
                required_skills=state["required_skills"],
                nice_to_have=state["nice_to_have"],
                evaluation_prompt=state["evaluation_prompt"],
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            if self.session:
                self.session.add(position)
                self.session.flush()
                state["position_id"] = position.position_id

            state["creation_error"] = None
            state["message"] = f"✓ 岗位创建成功 (ID: {position.position_id})"

            logger.info(f"✓ 岗位创建成功: {position.position_id}")

        except Exception as e:
            logger.error(f"✗ 创建失败: {str(e)}")
            state["creation_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"创建失败: {str(e)}"

        return state

    def node_reallocate_candidates(self, state: PositionAnalysisState) -> PositionAnalysisState:
        """节点：重新分配候选人"""
        logger.info("🔄 [节点] 重新分配候选人...")

        if not state["position_id"]:
            logger.warning("⏭️ 跳过：岗位创建失败")
            state["status"] = "error"
            return state

        try:
            if self.session:
                from models import Position
                position = self.session.query(Position).filter(
                    Position.position_id == state["position_id"]
                ).first()

                # 【修改】只调用有明确意向的候选人重新分配
                # 无明确意向的候选人不再自动重新分配（符合业务需求）
                explicit_changes = self.service._reallocate_explicit_intention_candidates(position)

                state["reallocation_changes"] = explicit_changes
            else:
                state["reallocation_changes"] = []

            state["reallocation_error"] = None
            state["message"] = f"✓ 重新分配完成: {len(state['reallocation_changes'])} 人受影响"
            state["status"] = "success"

            logger.info(f"✓ 重新分配完成: {len(state['reallocation_changes'])} 人受影响")

        except Exception as e:
            logger.error(f"✗ 重新分配失败: {str(e)}")
            state["reallocation_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"重新分配失败: {str(e)}"

        return state


# ==================== 查询工作流节点 ====================

class QueryNodes:
    """自然语言查询工作流的所有节点"""

    def __init__(self, llm_service: LLMService, service: RecruitmentService, session: Session = None):
        self.llm = llm_service
        self.service = service
        self.session = session

    def node_understand_query(self, state: QueryState) -> QueryState:
        """节点：理解查询意图"""
        logger.info(f"🔄 [节点] 理解查询: {state['natural_language_query']}")

        try:
            understanding = self.llm.understand_natural_language_query(
                state["natural_language_query"]
            )

            state["query_type"] = understanding.get("query_type", "unknown")
            state["query_params"] = understanding.get("params", {})
            state["understanding_error"] = None
            state["status"] = "executing"
            state["message"] = f"✓ 理解完成: {state['query_type']}"

            logger.info(f"✓ 查询类型: {state['query_type']}")

        except Exception as e:
            logger.error(f"✗ 理解失败: {str(e)}")
            state["understanding_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"理解失败: {str(e)}"

        return state

    def node_execute_query(self, state: QueryState) -> QueryState:
        """节点：执行查询"""
        logger.info("🔄 [节点] 执行查询...")

        if state["understanding_error"]:
            logger.warning("⏭️ 跳过：理解失败")
            state["status"] = "error"
            return state

        try:
            # 调用原有的查询逻辑
            results = self.service.execute_query(
                query_type=state["query_type"],
                params=state["query_params"]
            )

            state["query_results"] = results.get("results", [])
            state["total_count"] = results.get("total", 0)
            state["query_error"] = None
            state["status"] = "summarizing"
            state["message"] = f"✓ 查询完成: {state['total_count']} 条结果"

            logger.info(f"✓ 查询完成: {state['total_count']} 条结果")

        except Exception as e:
            logger.error(f"✗ 查询失败: {str(e)}")
            state["query_error"] = str(e)
            state["status"] = "error"
            state["message"] = f"查询失败: {str(e)}"

        return state

    def node_generate_summary(self, state: QueryState) -> QueryState:
        """节点：生成结果总结"""
        logger.info("🔄 [节点] 生成结果总结...")

        if state["query_error"]:
            logger.warning("⏭️ 跳过：查询失败")
            state["status"] = "error"
            return state

        try:
            summary = self.llm.generate_query_summary(
                state["natural_language_query"],
                state["query_results"]
            )

            state["summary"] = summary.get("summary", "")
            state["recommendation"] = summary.get("recommendation")
            state["summary_error"] = None
            state["status"] = "success"
            state["message"] = "✓ 完成"

            logger.info("✓ 总结生成完成")

        except Exception as e:
            logger.error(f"✗ 总结生成失败: {str(e)}")
            state["summary_error"] = str(e)
            state["status"] = "success"  # 但继续，总结失败不影响结果
            state["message"] = "✓ 查询成功（总结生成失败）"

        return state