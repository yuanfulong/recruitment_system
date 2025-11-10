"""
FastAPI主应用
"""
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# ==================== 加载环境变量 ====================
load_dotenv()

# ==================== 路径配置 ====================
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///recruitment.db")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional

from models import init_db, get_session, Position, Candidate, CandidatePositionMatch
from schemas import (
    PositionCreateSchema, CandidateDetailSchema, QueryRequestSchema,
    ErrorResponseSchema, SuccessResponseSchema
)
from service import RecruitmentService
from llm_service import create_llm_service

# ==================== 初始化 ====================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化数据库和LLM
try:
    engine = init_db(DATABASE_URL)
    logger.info("✓ 数据库初始化成功")
except Exception as e:
    logger.error(f"✗ 数据库初始化失败: {str(e)}")
    raise

if not ANTHROPIC_API_KEY:
    logger.warning("⚠ 未设置ANTHROPIC_API_KEY环境变量")

llm_service = create_llm_service(ANTHROPIC_API_KEY)
logger.info("✓ LLM服务初始化成功")


# ==================== 自动初始化数据 ====================

def init_default_positions():
    """如果数据库为空，自动创建默认岗位"""
    try:
        db = get_session(engine)
        position_count = db.query(Position).count()

        if position_count == 0:
            logger.info("📋 数据库为空，自动创建默认岗位...")

            # 定义默认岗位
            default_positions = [
                {
                    "name": "Python后端工程师",
                    "description": "负责API开发、数据库设计、系统架构设计。要求有Python编程经验，熟悉Web框架，掌握SQL数据库。"
                },
                {
                    "name": "Java后端开发",
                    "description": "负责Java后端系统开发、微服务架构设计。要求有Java编程经验3年+，熟悉Spring框架。"
                },
                {
                    "name": "前端开发工程师",
                    "description": "负责前端界面开发、用户体验优化。要求掌握React或Vue，HTML/CSS/JavaScript基础扎实。"
                },
                {
                    "name": "DevOps工程师",
                    "description": "负责基础设施建设、容器化部署、CI/CD流程。要求掌握Docker、Kubernetes、Linux系统。"
                },
                {
                    "name": "数据分析师",
                    "description": "负责数据分析、BI报表开发。要求掌握SQL、Python/R，有数据可视化经验。"
                }
            ]

            # 用LLM分析每个岗位并创建
            service = RecruitmentService(db, llm_service)

            for pos_data in default_positions:
                try:
                    logger.info(f"  → 创建岗位: {pos_data['name']}")

                    # LLM分析岗位
                    position_analysis = llm_service.analyze_position(
                        pos_data['name'],
                        pos_data['description']
                    )

                    # 创建岗位
                    position = Position(
                        name=pos_data['name'],
                        description=pos_data['description'],
                        base_score=60,
                        required_skills=position_analysis.get("required_skills", []),
                        nice_to_have=position_analysis.get("nice_to_have", []),
                        evaluation_prompt=position_analysis.get("evaluation_prompt", ""),
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )

                    db.add(position)
                    db.flush()

                    logger.info(f"    ✓ {pos_data['name']} 创建成功")

                except Exception as e:
                    logger.warning(f"    ✗ 创建 {pos_data['name']} 失败: {str(e)}")

            db.commit()
            logger.info("✓ 默认岗位初始化完成")
        else:
            logger.info(f"✓ 数据库已有 {position_count} 个岗位，跳过初始化")

        db.close()

    except Exception as e:
        logger.error(f"✗ 初始化数据失败: {str(e)}")


# 启动时自动初始化
init_default_positions()

# 创建FastAPI应用
app = FastAPI(
    title="智能招聘助手系统",
    description="基于LLM的简历提取与岗位匹配系统",
    version="1.0.0"
)

# ==================== CORS 配置 ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 挂载前端文件 ====================
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")
    logger.info(f"✓ 前端文件已挂载: {frontend_dir}")
else:
    logger.warning(f"⚠ 前端目录不存在: {frontend_dir}")


# ==================== 依赖注入 ====================

def get_db():
    """获取数据库会话"""
    db = get_session(engine)
    try:
        yield db
    finally:
        db.close()


def get_service(db: Session = Depends(get_db)) -> RecruitmentService:
    """获取招聘服务"""
    return RecruitmentService(db, llm_service)


# ==================== 初始化检查 ====================

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """健康检查"""
    try:
        # 检查数据库连接
        db.query(Position).first()

        # 检查岗位库状态
        position_count = db.query(Position).filter(Position.is_active == True).count()
        candidate_count = db.query(Candidate).count()

        return {
            "status": "healthy",
            "database": "connected",
            "positions": position_count,
            "candidates": candidate_count,
            "system_ready": position_count > 0
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


# ==================== 岗位管理 API ====================

@app.post("/api/positions")
def create_position(request: PositionCreateSchema,
                    service: RecruitmentService = Depends(get_service)):
    """
    创建新岗位

    - 自动触发重新分配
    - 返回变化报告
    """
    result = service.create_position(
        name=request.name,
        description=request.description,
        required_skills=request.required_skills,
        nice_to_have=request.nice_to_have
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result)

    return result


@app.get("/api/positions")
def list_positions(db: Session = Depends(get_db)):
    """
    列表查询所有活跃岗位
    """
    positions = db.query(Position).filter(Position.is_active == True).all()

    return {
        "total": len(positions),
        "positions": [
            {
                "position_id": p.position_id,
                "name": p.name,
                "description": p.description[:100] + "..." if len(p.description or "") > 100 else p.description,
                "base_score": p.base_score,
                "total_candidates": p.total_candidates,
                "qualified_count": p.qualified_count,
                "grade_distribution": {
                    "A": p.a_grade_count,
                    "B": p.b_grade_count,
                    "C": p.c_grade_count,
                    "D": p.d_grade_count
                },
                "created_at": p.created_at.isoformat()
            }
            for p in positions
        ]
    }


@app.get("/api/positions/{position_id}")
def get_position(position_id: int, db: Session = Depends(get_db)):
    """
    获取单个岗位详情
    """
    position = db.query(Position).filter(Position.position_id == position_id).first()

    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")

    return {
        "position_id": position.position_id,
        "name": position.name,
        "description": position.description,
        "base_score": position.base_score,
        "required_skills": position.required_skills,
        "nice_to_have": position.nice_to_have,
        "evaluation_prompt": position.evaluation_prompt,
        "total_candidates": position.total_candidates,
        "qualified_count": position.qualified_count,
        "grade_distribution": {
            "A": position.a_grade_count,
            "B": position.b_grade_count,
            "C": position.c_grade_count,
            "D": position.d_grade_count
        }
    }


@app.get("/api/positions/{position_id}/candidates")
def get_position_candidates(position_id: int,
                            min_grade: Optional[str] = Query("C"),
                            db: Session = Depends(get_db)):
    """
    获取某岗位的所有达标候选人

    - 按分数排序
    - 支持按等级过滤
    """
    position = db.query(Position).filter(Position.position_id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # 等级映射
    grade_map = {"A": 4, "B": 3, "C": 2, "D": 1}
    min_grade_val = grade_map.get(min_grade, 2)
    grade_vals = [g for g, v in grade_map.items() if grade_map[g] >= min_grade_val]

    matches = db.query(CandidatePositionMatch).join(Candidate).filter(
        CandidatePositionMatch.position_id == position_id,
        CandidatePositionMatch.overall_score >= 60,
        CandidatePositionMatch.grade.in_(grade_vals)
    ).order_by(CandidatePositionMatch.overall_score.desc()).all()

    candidates = []
    for match in matches:
        candidate = match.candidate
        candidates.append({
            "candidate_id": candidate.candidate_id,
            "name": candidate.name,
            "age": candidate.age,
            "email": candidate.email,
            "score": match.overall_score,
            "grade": match.grade,
            "evaluation_reason": match.evaluation_reason,
            "is_primary": candidate.auto_matched_position == position.name,
            "has_explicit_position": candidate.has_explicit_position,
            "uploaded_at": candidate.uploaded_at.isoformat()
        })

    return {
        "position_id": position_id,
        "position_name": position.name,
        "total_candidates": len(candidates),
        "candidates": candidates
    }


# ==================== 候选人管理 API ====================

@app.post("/api/candidates/upload")
async def upload_resume(file: UploadFile = File(...),
                        service: RecruitmentService = Depends(get_service)):
    """
    上传简历PDF
    """
    try:
        logger.info(f"开始上传文件: {file.filename}")

        # 检查文件类型
        if not file.filename.lower().endswith('.pdf'):
            return {
                "status": "error",
                "message": "只支持PDF文件"
            }

        contents = await file.read()
        logger.info(f"文件读取完成，大小: {len(contents)} 字节")

        result = service.process_resume(contents, file.filename)
        logger.info(f"简历处理完成: {result}")

        if result.get("status") == "error":
            logger.error(f"简历处理失败: {result}")
            return result

        return result

    except Exception as e:
        logger.error(f"上传失败: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"上传失败: {str(e)}"
        }
@app.get("/api/candidates/{candidate_id}")
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """
    获取候选人详情
    """
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    # 获取所有岗位评分
    matches = db.query(CandidatePositionMatch).join(Position).filter(
        CandidatePositionMatch.candidate_id == candidate_id
    ).order_by(CandidatePositionMatch.overall_score.desc()).all()

    positions = [
        {
            "position_name": match.position.name,
            "score": match.overall_score,
            "grade": match.grade,
            "is_primary": candidate.auto_matched_position == match.position.name
        }
        for match in matches
    ]

    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "age": candidate.age,
        "email": candidate.email,
        "phone": candidate.phone,
        "extraction_quality": candidate.extraction_quality,

        "has_explicit_position": candidate.has_explicit_position,
        "explicit_position": candidate.explicit_position,
        "is_position_locked": candidate.is_position_locked,
        "no_matched_position": candidate.no_matched_position,

        "auto_matched_position": candidate.auto_matched_position,
        "auto_matched_position_score": candidate.auto_matched_position_score,

        "positions": positions,
        "uploaded_at": candidate.uploaded_at.isoformat(),
        "last_reallocation_at": candidate.last_reallocation_at.isoformat() if candidate.last_reallocation_at else None,
        "reallocation_count": candidate.reallocation_count
    }


@app.get("/api/candidates")
def list_candidates(db: Session = Depends(get_db),
                    skip: int = Query(0, ge=0),
                    limit: int = Query(20, ge=1, le=100)):
    """
    列表查询候选人
    """
    candidates = db.query(Candidate).offset(skip).limit(limit).all()
    total = db.query(Candidate).count()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "name": c.name,
                "age": c.age,
                "auto_matched_position": c.auto_matched_position,
                "auto_matched_score": c.auto_matched_position_score,
                "is_position_locked": c.is_position_locked,
                "uploaded_at": c.uploaded_at.isoformat()
            }
            for c in candidates
        ]
    }


# ==================== 查询 API ====================

@app.post("/api/query")
def natural_language_query(request: QueryRequestSchema,
                           db: Session = Depends(get_db),
                           service: RecruitmentService = Depends(get_service)):
    """
    自然语言查询

    LLM理解查询意图 → 转换为SQL → 执行查询 → 生成总结
    """
    try:
        # LLM理解查询
        query_params = service.llm.understand_natural_language_query(request.query)

        # 根据查询类型执行不同的查询逻辑
        results = []

        if query_params.get("query_type") == "position_candidates":
            # 查询某岗位的候选人
            position_name = query_params.get("filters", {}).get("position_name")
            min_grade = query_params.get("filters", {}).get("min_grade", "C")

            if not position_name:
                return {"error": "缺少岗位名称"}

            position = db.query(Position).filter(Position.name.ilike(f"%{position_name}%")).first()
            if not position:
                return {"total": 0, "results": [], "message": "未找到相关岗位"}

            # 构建查询
            from sqlalchemy import and_
            matches = db.query(CandidatePositionMatch).join(Candidate).filter(
                and_(
                    CandidatePositionMatch.position_id == position.position_id,
                    CandidatePositionMatch.overall_score >= 60
                )
            ).order_by(CandidatePositionMatch.overall_score.desc()).all()

            results = [
                {
                    "candidate_name": m.candidate.name,
                    "score": m.overall_score,
                    "grade": m.grade,
                    "email": m.candidate.email
                }
                for m in matches
            ]

        elif query_params.get("query_type") == "candidate_positions":
            # 查询候选人在各岗位的表现
            candidate_id = query_params.get("filters", {}).get("candidate_id")

            if not candidate_id:
                return {"error": "缺少候选人ID"}

            matches = db.query(CandidatePositionMatch).join(Position).filter(
                CandidatePositionMatch.candidate_id == candidate_id
            ).order_by(CandidatePositionMatch.overall_score.desc()).all()

            results = [
                {
                    "position_name": m.position.name,
                    "score": m.overall_score,
                    "grade": m.grade
                }
                for m in matches
            ]

        elif query_params.get("query_type") == "statistics":
            # 统计查询
            position_count = db.query(Position).filter(Position.is_active == True).count()
            candidate_count = db.query(Candidate).count()
            qualified_count = db.query(CandidatePositionMatch).filter(
                CandidatePositionMatch.overall_score >= 60
            ).count()

            results = [
                {
                    "metric": "总岗位数",
                    "value": position_count
                },
                {
                    "metric": "总候选人数",
                    "value": candidate_count
                },
                {
                    "metric": "达标候选人数",
                    "value": qualified_count
                }
            ]

        # LLM生成总结
        summary = service.llm.generate_query_summary(results, request.query)

        return {
            "query": request.query,
            "query_type": query_params.get("query_type"),
            "total": len(results),
            "results": results,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        return {
            "error": f"查询失败: {str(e)}"
        }


# ==================== 根路径 ====================

@app.get("/")
def root():
    """
    API文档和快速开始指南
    """
    return {
        "message": "欢迎使用智能招聘助手系统 v1.0",
        "quick_start": {
            "step1": "创建岗位: POST /api/positions",
            "step2": "上传简历: POST /api/candidates/upload",
            "step3": "查询候选人: GET /api/candidates",
            "step4": "自然语言查询: POST /api/query"
        },
        "frontend": "/ui",
        "documentation": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)