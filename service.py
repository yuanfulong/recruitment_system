"""
核心业务逻辑模块
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import (
    Candidate, Position, CandidatePositionMatch,
    PositionAllocationHistory, AuditLog, CandidateVersion
)
from schemas import (
    CandidateExtractSchema, IntentionAnalysisSchema,
    EvaluationResultSchema, ReallocationChangeSchema,
    BatchReallocationResultSchema
)
from llm_service import LLMService
from pdf_processor import process_pdf_bytes

logger = logging.getLogger(__name__)


class RecruitmentService:
    """招聘服务类 - 核心业务逻辑"""

    def __init__(self, session: Session, llm_service: LLMService):
        self.session = session
        self.llm = llm_service

    # ==================== 位置1：简历处理 ====================

    def process_resume(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        处理上传的简历

        流程：
        1. 检查岗位库
        2. PDF解析
        3. 信息提取
        4. 求职意向分析
        5. 对所有岗位评分
        6. 分配最优岗位
        7. 入库保存
        """

        # Step 1: 检查岗位库
        positions = self.session.query(Position).filter(Position.is_active == True).all()
        if not positions:
            return {
                "status": "error",
                "code": "POSITION_DB_EMPTY",
                "message": "岗位库为空，请先添加岗位",
                "action": "请通过 POST /api/positions 创建岗位"
            }

        # Step 2: PDF解析
        try:
            text, metadata = process_pdf_bytes(file_bytes)
        except Exception as e:
            return {
                "status": "error",
                "message": f"PDF解析失败: {str(e)}"
            }

        # Step 3: 信息提取
        try:
            candidate_info = self.llm.extract_candidate_info(text)
        except Exception as e:
            logger.error(f"信息提取失败: {str(e)}")
            return {
                "status": "error",
                "message": f"信息提取失败: {str(e)}"
            }

        # Step 4: 求职意向分析
        try:
            intention = self.llm.analyze_job_intention(candidate_info)
        except Exception as e:
            logger.error(f"意向分析失败: {str(e)}")
            intention = {
                "has_explicit_position": False,
                "explicit_position": None,
                "explicit_position_source": None,
                "reasoning": "分析失败，默认为无明确意向"
            }

        # Step 5: 对所有岗位评分
        evaluations = {}
        for position in positions:
            try:
                eval_result = self.llm.evaluate_candidate_for_position(
                    candidate_info,
                    position.name,
                    position.description,
                    position.required_skills or []
                )
                evaluations[position.position_id] = eval_result
            except Exception as e:
                logger.warning(f"对岗位{position.name}的评分失败: {str(e)}")
                # 降级处理：给一个默认的低分
                evaluations[position.position_id] = {
                    "overall_score": 0,
                    "grade": "D",
                    "evaluation_reason": f"评分失败: {str(e)}",
                    "matches": [],
                    "gaps": [],
                    "potential": "unknown"
                }

        # Step 6: 分配最优岗位
        best_position_id, best_score = self._find_best_position(evaluations)
        best_position = self.session.query(Position).filter(
            Position.position_id == best_position_id
        ).first() if best_position_id else None

        # 判断分配决策
        is_locked = False
        no_matched = False
        auto_matched_position = best_position.name if best_position else None

        if intention.get("has_explicit_position"):
            # 检查意向岗位是否存在
            explicit_pos = self.session.query(Position).filter(
                Position.name == intention.get("explicit_position")
            ).first()

            if explicit_pos:
                # 情况1：意向岗位存在
                is_locked = True
                auto_matched_position = explicit_pos.name
                best_position_id = explicit_pos.position_id
                best_score = evaluations.get(explicit_pos.position_id, {}).get("overall_score", 60)
            else:
                # 情况2：意向岗位不存在
                no_matched = True
                # 保持best_position（当前最优）

        # Step 7: 入库保存
        try:
            candidate = Candidate(
                name=candidate_info.get("name", "未知"),
                age=candidate_info.get("age"),
                email=candidate_info.get("email"),
                phone=candidate_info.get("phone"),

                skills_json=candidate_info.get("skills", []),
                work_experience=str(candidate_info.get("work_experience", [])),
                education=str(candidate_info.get("education", [])),
                certifications=str(candidate_info.get("certifications", [])),
                self_evaluation=candidate_info.get("self_evaluation"),

                extraction_quality=candidate_info.get("extraction_quality", 0),

                has_explicit_position=intention.get("has_explicit_position", False),
                explicit_position=intention.get("explicit_position"),
                explicit_position_source=intention.get("explicit_position_source"),

                no_matched_position=no_matched,
                auto_matched_position=auto_matched_position,
                auto_matched_position_score=best_score,
                is_position_locked=is_locked,

                uploaded_at=datetime.utcnow()
            )

            self.session.add(candidate)
            self.session.flush()  # 获取candidate_id

            # 保存版本历史
            version = CandidateVersion(
                candidate_id=candidate.candidate_id,
                snapshot_json=candidate_info,
                uploaded_at=datetime.utcnow(),
                notes=f"初始上传: {filename}"
            )
            self.session.add(version)

            # 保存所有匹配记录
            for position_id, eval_result in evaluations.items():
                match = CandidatePositionMatch(
                    candidate_id=candidate.candidate_id,
                    position_id=position_id,
                    overall_score=eval_result.get("overall_score", 0),
                    grade=eval_result.get("grade", "D"),
                    evaluation_reason=eval_result.get("evaluation_reason", ""),
                    is_qualified=eval_result.get("overall_score", 0) >= 60,
                    evaluated_at=datetime.utcnow(),
                    evaluation_method="INITIAL"
                )
                self.session.add(match)

            self.session.commit()

            # 审计日志
            self._log_audit(
                action="RESUME_UPLOADED",
                candidate_id=candidate.candidate_id,
                details={
                    "filename": filename,
                    "has_explicit_position": intention.get("has_explicit_position"),
                    "is_locked": is_locked
                }
            )

            return {
                "status": "success",
                "candidate_id": candidate.candidate_id,
                "name": candidate.name,
                "auto_matched_position": auto_matched_position,
                "auto_matched_score": best_score,
                "is_position_locked": is_locked,
                "no_matched_position": no_matched,
                "extraction_quality": candidate_info.get("extraction_quality", 0)
            }

        except Exception as e:
            logger.error(f"数据保存失败: {str(e)}", exc_info=True)
            self.session.rollback()
            return {
                "status": "error",
                "message": f"数据保存失败: {str(e)}"
            }

    # ==================== 位置2：岗位创建 ====================

    def create_position(
            self,
            name: str,
            description: str,
            required_skills: Optional[List[str]] = None,
            nice_to_have: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        创建新岗位

        流程：
        1. LLM分析岗位
        2. 保存岗位
        3. 【修改】只处理有明确意向的候选人（不处理无意向候选人）
        4. 返回变化报告
        """

        # Step 1: LLM分析岗位
        try:
            position_analysis = self.llm.analyze_position(name, description)
        except Exception as e:
            logger.error(f"岗位分析失败: {str(e)}")
            return {
                "status": "error",
                "message": f"岗位分析失败: {str(e)}"
            }

        # Step 2: 保存岗位
        try:
            position = Position(
                name=name,
                description=description,
                base_score=60,
                required_skills=position_analysis.get("required_skills", []),
                nice_to_have=position_analysis.get("nice_to_have", []),
                evaluation_prompt=position_analysis.get("evaluation_prompt", ""),
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            self.session.add(position)
            self.session.flush()
            position_id = position.position_id
            logger.info(f"岗位已创建: {position_id} - {name}")

        except Exception as e:
            logger.error(f"岗位创建失败: {str(e)}")
            return {
                "status": "error",
                "message": f"岗位创建失败: {str(e)}"
            }

        # Step 3: 【修改】只处理有明确意向的候选人
        try:
            changes = self._reallocate_explicit_intention_candidates(position)
        except Exception as e:
            logger.error(f"处理有意向候选人失败: {str(e)}")
            changes = []

        # 【删除】不再处理无意向候选人
        # 原代码中这里会调用 self.batch_reallocate_on_new_position(position_id)
        # 现在已移除

        # Step 4: 提交
        self.session.commit()

        # 审计日志
        self._log_audit(
            action="CREATE_POSITION",
            position_id=position_id,
            details={
                "position_name": name,
                "changes_count": len(changes)
            }
        )

        return {
            "status": "success",
            "position_id": position_id,
            "position_name": name,
            "reallocation_result": {
                "total_candidates_scanned": len(changes),
                "candidates_reallocated": len(changes),
                "changes": changes
            }
        }

    # ==================== 位置3：重新分配逻辑（已修改） ====================

    def _reallocate_explicit_intention_candidates(
            self,
            new_position: Position
    ) -> List[Dict[str, Any]]:
        """
        【修改】只处理有明确意向的候选人

        处理逻辑：
        - 查询所有 has_explicit_position=True 且 no_matched_position=True 的候选人
        - 检查新岗位是否与其明确意向匹配
        - 匹配 → 更新分配、锁定、完成
        - 不匹配 → 保持现状

        【不再】处理无意向候选人
        """

        changes = []

        # 只查询有明确意向但岗位未找到的候选人
        all_candidates = self.session.query(Candidate).filter(
            Candidate.has_explicit_position == True,
            Candidate.no_matched_position == True,
            Candidate.is_position_locked == False
        ).all()

        for candidate in all_candidates:
            try:
                # 判断新岗位是否与意向匹配
                match_result = self.llm.match_position_to_intention(
                    candidate.explicit_position,
                    new_position.name,
                    new_position.description
                )

                if match_result.get("match") and match_result.get("confidence", 0) > 0.8:
                    # 匹配成功！
                    # 1. 对该岗位评分
                    candidate_info = {
                        "name": candidate.name,
                        "skills": candidate.skills_json or [],
                        "work_experience": candidate.work_experience,
                        "education": candidate.education
                    }

                    eval_result = self.llm.evaluate_candidate_for_position(
                        candidate_info,
                        new_position.name,
                        new_position.description,
                        new_position.required_skills or []
                    )

                    old_pos = candidate.auto_matched_position
                    old_score = candidate.auto_matched_position_score
                    new_score = eval_result.get("overall_score", 60)

                    # 2. 更新候选人
                    candidate.auto_matched_position = new_position.name
                    candidate.auto_matched_position_score = new_score
                    candidate.is_position_locked = True
                    candidate.no_matched_position = False
                    candidate.last_reallocation_at = datetime.utcnow()
                    candidate.reallocation_count += 1

                    # 3. 记录变化
                    history = PositionAllocationHistory(
                        candidate_id=candidate.candidate_id,
                        old_position=old_pos,
                        old_score=old_score,
                        new_position=new_position.name,
                        new_score=new_score,
                        trigger_event="NEW_POSITION",
                        reallocated_at=datetime.utcnow(),
                        reason="求职意向岗位已创建"
                    )
                    self.session.add(history)

                    # 4. 新增match记录
                    match = CandidatePositionMatch(
                        candidate_id=candidate.candidate_id,
                        position_id=new_position.position_id,
                        overall_score=new_score,
                        grade=eval_result.get("grade", "C"),
                        evaluation_reason=eval_result.get("evaluation_reason", ""),
                        is_qualified=new_score >= 60,
                        evaluated_at=datetime.utcnow(),
                        evaluation_method="BATCH"
                    )
                    self.session.add(match)

                    changes.append({
                        "candidate_id": candidate.candidate_id,
                        "candidate_name": candidate.name,
                        "reason": "求职意向岗位已创建",
                        "old_position": old_pos,
                        "old_score": old_score,
                        "new_position": new_position.name,
                        "new_score": new_score,
                        "score_improvement": new_score - (old_score or 0)
                    })

            except Exception as e:
                logger.warning(f"岗位匹配判断失败 ({candidate.candidate_id}): {str(e)}")

        # 审计日志
        self._log_audit(
            action="REALLOCATE_EXPLICIT_INTENTION",
            position_id=new_position.position_id,
            details={
                "total_candidates": len(all_candidates),
                "reallocated": len(changes),
                "changes": changes
            }
        )

        return changes

    # ==================== 位置4：process_resume_save（agent_nodes需要） ====================

    def process_resume_save(self, candidate_info: Dict, job_intention: Dict,
                            evaluations: Dict, allocation_decision: Dict,
                            filename: str) -> Dict[str, Any]:
        """
        保存候选人到数据库
        （agent_nodes调用的方法）
        """
        try:
            candidate = Candidate(
                name=candidate_info.get("name", "未知"),
                age=candidate_info.get("age"),
                email=candidate_info.get("email"),
                phone=candidate_info.get("phone"),

                skills_json=candidate_info.get("skills", []),
                work_experience=str(candidate_info.get("work_experience", [])),
                education=str(candidate_info.get("education", [])),
                certifications=str(candidate_info.get("certifications", [])),
                self_evaluation=candidate_info.get("self_evaluation"),

                extraction_quality=candidate_info.get("extraction_quality", 0),

                has_explicit_position=job_intention.get("has_explicit_position", False),
                explicit_position=job_intention.get("explicit_position"),
                explicit_position_source=job_intention.get("explicit_position_source"),

                no_matched_position=allocation_decision.get("no_matched_position", False),
                auto_matched_position=allocation_decision.get("auto_matched_position"),
                auto_matched_position_score=allocation_decision.get("auto_matched_position_score"),
                is_position_locked=allocation_decision.get("is_position_locked", False),

                uploaded_at=datetime.utcnow()
            )

            self.session.add(candidate)
            self.session.flush()
            candidate_id = candidate.candidate_id

            # 保存版本历史
            version = CandidateVersion(
                candidate_id=candidate_id,
                snapshot_json=candidate_info,
                uploaded_at=datetime.utcnow(),
                notes=f"初始上传: {filename}"
            )
            self.session.add(version)

            # 保存所有匹配记录
            for position_id, eval_result in evaluations.items():
                match = CandidatePositionMatch(
                    candidate_id=candidate_id,
                    position_id=position_id,
                    overall_score=eval_result.get("overall_score", 0),
                    grade=eval_result.get("grade", "D"),
                    evaluation_reason=eval_result.get("evaluation_reason", ""),
                    is_qualified=eval_result.get("overall_score", 0) >= 60,
                    evaluated_at=datetime.utcnow(),
                    evaluation_method="INITIAL"
                )
                self.session.add(match)

            self.session.commit()

            self._log_audit(
                action="RESUME_UPLOADED",
                candidate_id=candidate_id,
                details={
                    "filename": filename,
                    "has_explicit_position": job_intention.get("has_explicit_position"),
                    "is_locked": allocation_decision.get("is_position_locked")
                }
            )

            return {
                "status": "success",
                "candidate_id": candidate_id,
                "name": candidate.name
            }

        except Exception as e:
            logger.error(f"数据保存失败: {str(e)}", exc_info=True)
            self.session.rollback()
            raise

    # ==================== 位置5：execute_query（agent_nodes需要） ====================

    def execute_query(self, query_type: str, params: Dict) -> Dict[str, Any]:
        """
        执行结构化查询
        （agent_nodes调用的方法）
        """
        results = []
        total = 0

        if query_type == "position_candidates":
            # 查询某岗位的候选人
            position_name = params.get("position_name")
            min_grade = params.get("min_grade", "D")

            position = self.session.query(Position).filter(
                Position.name.ilike(f"%{position_name}%")
            ).first()

            if position:
                from sqlalchemy import and_
                matches = self.session.query(CandidatePositionMatch).join(Candidate).filter(
                    and_(
                        CandidatePositionMatch.position_id == position.position_id,
                        CandidatePositionMatch.overall_score >= 60
                    )
                ).order_by(CandidatePositionMatch.overall_score.desc()).all()

                results = [
                    {
                        "candidate_id": m.candidate.candidate_id,
                        "candidate_name": m.candidate.name,
                        "score": m.overall_score,
                        "grade": m.grade,
                        "email": m.candidate.email,
                        "phone": m.candidate.phone
                    }
                    for m in matches
                ]
                total = len(results)

        elif query_type == "candidate_positions":
            # 查询某候选人的各岗位表现
            candidate_name = params.get("candidate_name")

            candidate = self.session.query(Candidate).filter(
                Candidate.name.ilike(f"%{candidate_name}%")
            ).first()

            if candidate:
                matches = self.session.query(CandidatePositionMatch).filter(
                    CandidatePositionMatch.candidate_id == candidate.candidate_id
                ).order_by(CandidatePositionMatch.overall_score.desc()).all()

                results = [
                    {
                        "position_name": m.position.name,
                        "score": m.overall_score,
                        "grade": m.grade,
                        "evaluation_reason": m.evaluation_reason
                    }
                    for m in matches
                ]
                total = len(results)

        elif query_type == "high_quality_candidates":
            # 查询高质量候选人
            min_score = params.get("min_score", 70)

            matches = self.session.query(CandidatePositionMatch).filter(
                CandidatePositionMatch.overall_score >= min_score
            ).order_by(CandidatePositionMatch.overall_score.desc()).all()

            results = [
                {
                    "candidate_name": m.candidate.name,
                    "position_name": m.position.name,
                    "score": m.overall_score,
                    "grade": m.grade
                }
                for m in matches
            ]
            total = len(results)

        return {
            "results": results,
            "total": total,
            "query_type": query_type
        }

    # ==================== 位置6：辅助方法 ====================

    def _find_best_position(self, evaluations: Dict[int, Dict]) -> Tuple[int, int]:
        """找到候选人分数最高的岗位"""
        if not evaluations:
            return None, 0

        best_pos_id = None
        best_score = -1

        for pos_id, eval_result in evaluations.items():
            score = eval_result.get("overall_score", 0)
            if score > best_score:
                best_score = score
                best_pos_id = pos_id

        return best_pos_id, best_score

    def _log_audit(self, action: str, candidate_id: int = None,
                   position_id: int = None, details: Dict = None):
        """记录审计日志"""
        try:
            log = AuditLog(
                operator="system",
                action=action,
                candidate_id=candidate_id,
                position_id=position_id,
                details=details,
                timestamp=datetime.utcnow()
            )
            self.session.add(log)
        except Exception as e:
            logger.warning(f"审计日志记录失败: {str(e)}")