"""
FastAPI主应用 - LangGraph版本
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
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional

from models import init_db, get_session, Position, Candidate, CandidatePositionMatch
from schemas import PositionCreateSchema, QueryRequestSchema
from service import RecruitmentService
from llm_service import create_llm_service
from agent_workflows import RecruitmentWorkflows

# ==================== 初始化 ====================

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

# 创建FastAPI应用
app = FastAPI(
    title="智能招聘助手系统",
    description="基于LangGraph的简历分析和岗位匹配系统",
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

# ==================== 【关键修复】挂载前端文件 ====================

# 【方案1】如果前端在 frontend/ 目录（推荐）
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_dir) and os.path.isfile(os.path.join(frontend_dir, "index.html")):
    app.mount("/ui", StaticFiles(directory=frontend_dir, html=True), name="ui")
    logger.info(f"✓ 前端已挂载: {frontend_dir}")
# 【方案2】如果前端是单个 index.html 文件在根目录
elif os.path.isfile(os.path.join(os.path.dirname(__file__), "index.html")):
    index_path = os.path.join(os.path.dirname(__file__), "index.html")


    @app.get("/ui", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(index_path)


    @app.get("/", include_in_schema=False)
    async def serve_root():
        return FileResponse(index_path)


    logger.info("✓ 前端已挂载: index.html")
else:
    logger.warning("⚠ 前端文件未找到，跳过挂载")
    logger.warning(f"  预期位置1: {frontend_dir}/index.html")
    logger.warning(f"  预期位置2: {os.path.dirname(__file__)}/index.html")


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


def get_workflows(db: Session = Depends(get_db)) -> RecruitmentWorkflows:
    """获取工作流"""
    service = RecruitmentService(db, llm_service)
    return RecruitmentWorkflows(db, llm_service, service)


# ==================== 初始化检查 ====================

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """健康检查"""
    try:
        db.query(Position).first()
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
def create_position(
        request: PositionCreateSchema,
        service: RecruitmentService = Depends(get_service)
):
    """创建新岗位"""
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
    """列表查询所有活跃岗位"""
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
                "created_at": p.created_at.isoformat()
            }
            for p in positions
        ]
    }


@app.get("/api/positions/{position_id}")
def get_position(position_id: int, db: Session = Depends(get_db)):
    """获取岗位详情"""
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
        "total_candidates": position.total_candidates,
        "qualified_count": position.qualified_count,
        "created_at": position.created_at.isoformat()
    }


@app.get("/api/positions/{position_id}/candidates")
def get_position_candidates(position_id: int, min_grade: str = Query("C"), db: Session = Depends(get_db)):
    """获取岗位的候选人列表"""
    position = db.query(Position).filter(Position.position_id == position_id).first()

    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # 获取该岗位的所有候选人
    matches = db.query(CandidatePositionMatch).filter(
        CandidatePositionMatch.position_id == position_id
    ).order_by(CandidatePositionMatch.overall_score.desc()).all()

    candidates = [
        {
            "candidate_id": m.candidate.candidate_id,
            "name": m.candidate.name,
            "score": m.overall_score,
            "grade": m.grade,
            "evaluation_reason": m.evaluation_reason,
            "email": m.candidate.email,
            "phone": m.candidate.phone
        }
        for m in matches if m.overall_score >= 60  # 只返回及格的
    ]

    return {
        "position_id": position_id,
        "position_name": position.name,
        "total_candidates": len(candidates),
        "candidates": candidates
    }


# ==================== 候选人管理 API ====================

@app.post("/api/candidates/upload")
async def upload_resume(
        file: UploadFile = File(...),
        service: RecruitmentService = Depends(get_service)
):
    """上传简历PDF"""
    try:
        logger.info(f"开始上传文件: {file.filename}")

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
    """获取候选人详情"""
    candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()

    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    # 获取候选人在各岗位的匹配度【修复】
    matches = db.query(CandidatePositionMatch).filter(
        CandidatePositionMatch.candidate_id == candidate_id
    ).order_by(CandidatePositionMatch.overall_score.desc()).all()

    positions = [
        {
            "position_name": m.position.name,
            "score": m.overall_score,
            "grade": m.grade,
            "evaluation_reason": m.evaluation_reason
        }
        for m in matches
    ]

    return {
        "candidate_id": candidate.candidate_id,
        "name": candidate.name,
        "age": candidate.age,
        "email": candidate.email,
        "phone": candidate.phone,
        "auto_matched_position": candidate.auto_matched_position,
        "auto_matched_position_score": candidate.auto_matched_position_score,
        "is_position_locked": candidate.is_position_locked,
        "no_matched_position": candidate.no_matched_position,
        "extraction_quality": candidate.extraction_quality,
        "uploaded_at": candidate.uploaded_at.isoformat(),
        "positions": positions  # 🆕 添加各岗位匹配度
    }


@app.get("/api/candidates")
def list_candidates(
        db: Session = Depends(get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100)
):
    """列表查询候选人"""
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
def natural_language_query(
        request: QueryRequestSchema,
        db: Session = Depends(get_db),
        service: RecruitmentService = Depends(get_service)
):
    """自然语言查询"""
    try:
        query_params = service.llm.understand_natural_language_query(request.query)
        results = []

        if query_params.get("query_type") == "position_candidates":
            position_name = query_params.get("filters", {}).get("position_name")
            if not position_name:
                return {"error": "缺少岗位名称"}

            position = db.query(Position).filter(Position.name.ilike(f"%{position_name}%")).first()
            if not position:
                return {"total": 0, "results": [], "message": "未找到相关岗位"}

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

        summary = service.llm.generate_query_summary(results, request.query)

        return {
            "query": request.query,
            "total": len(results),
            "results": results,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        return {"error": f"查询失败: {str(e)}"}


# ==================== 根路径 ====================

@app.get("/")
def root():
    """API文档和快速开始指南"""
    return {
        "message": "欢迎使用智能招聘助手系统 v1.0（LangGraph版本）",
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