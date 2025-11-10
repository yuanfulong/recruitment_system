"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import json

Base = declarative_base()

class Candidate(Base):
    """候选人表"""
    __tablename__ = "candidates"

    candidate_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    email = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)

    # 提取的信息
    skills_json = Column(JSON, nullable=True)
    work_experience = Column(Text, nullable=True)
    education = Column(Text, nullable=True)
    certifications = Column(Text, nullable=True)
    self_evaluation = Column(Text, nullable=True)

    # 提取质量
    extraction_quality = Column(Float, default=0.0)

    # 求职意向（关键字段）
    has_explicit_position = Column(Boolean, default=False)
    explicit_position = Column(String(100), nullable=True)
    explicit_position_source = Column(Text, nullable=True)

    # 新增：标志位（重要）
    no_matched_position = Column(Boolean, default=False)

    # 系统自动分配（可改动或固定）
    auto_matched_position = Column(String(100), nullable=True)
    auto_matched_position_score = Column(Integer, nullable=True)

    # 控制标志（新增）
    is_position_locked = Column(Boolean, default=False)

    # 版本和时间
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    last_reallocation_at = Column(DateTime, nullable=True)
    reallocation_count = Column(Integer, default=0)

    # 关系
    matches = relationship("CandidatePositionMatch", back_populates="candidate")
    versions = relationship("CandidateVersion", back_populates="candidate")
    allocation_history = relationship("PositionAllocationHistory", back_populates="candidate")

    def __repr__(self):
        return f"<Candidate {self.candidate_id}: {self.name}>"


class Position(Base):
    """岗位表"""
    __tablename__ = "positions"

    position_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    base_score = Column(Integer, default=60)

    # LLM提炼的要求
    required_skills = Column(JSON, nullable=True)
    nice_to_have = Column(JSON, nullable=True)
    evaluation_prompt = Column(Text, nullable=True)

    # 岗位状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 统计信息
    total_candidates = Column(Integer, default=0)
    qualified_count = Column(Integer, default=0)
    a_grade_count = Column(Integer, default=0)
    b_grade_count = Column(Integer, default=0)
    c_grade_count = Column(Integer, default=0)
    d_grade_count = Column(Integer, default=0)
    last_update_time = Column(DateTime, nullable=True)

    # 关系
    matches = relationship("CandidatePositionMatch", back_populates="position")

    def __repr__(self):
        return f"<Position {self.position_id}: {self.name}>"


class CandidatePositionMatch(Base):
    """候选人-岗位匹配记录表"""
    __tablename__ = "candidate_position_match"

    match_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.position_id"), nullable=False)

    # 评分信息
    overall_score = Column(Integer, nullable=False)
    grade = Column(String(1), nullable=False)  # A/B/C/D
    evaluation_reason = Column(Text, nullable=True)

    # 状态
    is_qualified = Column(Boolean, default=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow)
    evaluation_method = Column(String(50), nullable=True)

    # 追踪
    viewed_by_hr = Column(Boolean, default=False)
    last_viewed_at = Column(DateTime, nullable=True)

    # 关系
    candidate = relationship("Candidate", back_populates="matches")
    position = relationship("Position", back_populates="matches")

    def __repr__(self):
        return f"<Match {self.match_id}: Candidate{self.candidate_id} - Position{self.position_id} ({self.grade})>"


class PositionAllocationHistory(Base):
    """分配历史表"""
    __tablename__ = "position_allocation_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id"), nullable=False)
    old_position = Column(String(100), nullable=True)
    old_score = Column(Integer, nullable=True)
    new_position = Column(String(100), nullable=False)
    new_score = Column(Integer, nullable=False)

    trigger_event = Column(String(50), nullable=False)  # NEW_POSITION/MANUAL/AUTO_RERANK
    reallocated_at = Column(DateTime, default=datetime.utcnow)
    reallocated_by = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)

    # 关系
    candidate = relationship("Candidate", back_populates="allocation_history")

    def __repr__(self):
        return f"<AllocationHistory {self.history_id}: Candidate{self.candidate_id}>"


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_log"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    operator = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False)
    candidate_id = Column(Integer, nullable=True)
    position_id = Column(Integer, nullable=True)

    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog {self.log_id}: {self.action}>"


class CandidateVersion(Base):
    """候选人版本历史表"""
    __tablename__ = "candidate_version"

    version_id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.candidate_id"), nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    # 关系
    candidate = relationship("Candidate", back_populates="versions")

    def __repr__(self):
        return f"<CandidateVersion {self.version_id}: Candidate{self.candidate_id}>"


# 数据库初始化
# def init_db(database_url: str):
#     """初始化数据库"""
#     engine = create_engine(database_url)
#     Base.metadata.create_all(engine)
#     return engine
def init_db(database_url: str):
    """初始化数据库"""
    # SQLite特殊配置
    if "sqlite" in database_url:
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """获取数据库会话"""
    Session = sessionmaker(bind=engine)
    return Session()
