"""
LangGraph 工作流图构建
定义所有工作流的状态转移和边的连接
"""

import logging
from typing import Literal
from langgraph.graph import StateGraph, START, END
from agent_state import (
    ResumeProcessState, PositionAnalysisState, QueryState,
    create_resume_state, create_position_state, create_query_state
)
from agent_nodes import ResumeProcessingNodes, PositionAnalysisNodes, QueryNodes
from sqlalchemy.orm import Session
from llm_service import LLMService
from service import RecruitmentService

logger = logging.getLogger(__name__)


class WorkflowFactory:
    """工作流工厂 - 负责构建所有工作流"""

    def __init__(self, session: Session, llm_service: LLMService, service: RecruitmentService):
        self.session = session
        self.llm = llm_service
        self.service = service

        # 初始化所有节点处理器【修复】添加session参数
        self.resume_nodes = ResumeProcessingNodes(llm_service, service, session)
        self.position_nodes = PositionAnalysisNodes(llm_service, service, session)
        self.query_nodes = QueryNodes(llm_service, service, session)

    # ==================== 简历处理工作流 ====================

    def build_resume_processing_workflow(self):
        """
        构建简历处理工作流

        流程：
        START
          ↓
        extract_info (提取信息)
          ↓
        analyze_intention (分析求职意向)
          ↓
        evaluate_positions (评分所有岗位)
          ↓
        make_allocation_decision (做出分配决策)
          ↓
        save_to_database (保存到数据库)
          ↓
        END
        """

        logger.info("🏗️ 构建简历处理工作流...")

        workflow = StateGraph(ResumeProcessState)

        # 添加节点
        workflow.add_node("extract_info", self.resume_nodes.node_extract_info)
        workflow.add_node("analyze_intention", self.resume_nodes.node_analyze_intention)
        workflow.add_node("evaluate_positions", self.resume_nodes.node_evaluate_positions)
        workflow.add_node("make_allocation_decision", self.resume_nodes.node_make_allocation_decision)
        workflow.add_node("save_to_database", self.resume_nodes.node_save_to_database)

        # 添加边
        workflow.add_edge(START, "extract_info")
        workflow.add_edge("extract_info", "analyze_intention")
        workflow.add_edge("analyze_intention", "evaluate_positions")
        workflow.add_edge("evaluate_positions", "make_allocation_decision")
        workflow.add_edge("make_allocation_decision", "save_to_database")
        workflow.add_edge("save_to_database", END)

        graph = workflow.compile()
        logger.info("✓ 简历处理工作流构建完成")
        return graph

    # ==================== 岗位分析工作流 ====================

    def build_position_analysis_workflow(self):
        """
        构建岗位分析工作流

        流程：
        START
          ↓
        analyze_position (分析岗位要求)
          ↓
        create_position (创建岗位)
          ↓
        reallocate_candidates (重新分配候选人)
          ↓
        END
        """

        logger.info("🏗️ 构建岗位分析工作流...")

        workflow = StateGraph(PositionAnalysisState)

        # 添加节点
        workflow.add_node("analyze_position", self.position_nodes.node_analyze_position)
        workflow.add_node("create_position", self.position_nodes.node_create_position)
        workflow.add_node("reallocate_candidates", self.position_nodes.node_reallocate_candidates)

        # 添加边
        workflow.add_edge(START, "analyze_position")
        workflow.add_edge("analyze_position", "create_position")
        workflow.add_edge("create_position", "reallocate_candidates")
        workflow.add_edge("reallocate_candidates", END)

        graph = workflow.compile()
        logger.info("✓ 岗位分析工作流构建完成")
        return graph

    # ==================== 查询工作流 ====================

    def build_query_workflow(self):
        """
        构建自然语言查询工作流

        流程：
        START
          ↓
        understand_query (理解查询意图)
          ↓
        execute_query (执行查询)
          ↓
        generate_summary (生成结果总结)
          ↓
        END
        """

        logger.info("🏗️ 构建查询工作流...")

        workflow = StateGraph(QueryState)

        # 添加节点
        workflow.add_node("understand_query", self.query_nodes.node_understand_query)
        workflow.add_node("execute_query", self.query_nodes.node_execute_query)
        workflow.add_node("generate_summary", self.query_nodes.node_generate_summary)

        # 添加边
        workflow.add_edge(START, "understand_query")
        workflow.add_edge("understand_query", "execute_query")
        workflow.add_edge("execute_query", "generate_summary")
        workflow.add_edge("generate_summary", END)

        graph = workflow.compile()
        logger.info("✓ 查询工作流构建完成")
        return graph


class RecruitmentWorkflows:
    """
    所有招聘工作流的集合
    提供便捷的API调用
    """

    def __init__(self, session: Session, llm_service: LLMService, service: RecruitmentService):
        self.factory = WorkflowFactory(session, llm_service, service)

        # 编译所有工作流
        self.resume_workflow = self.factory.build_resume_processing_workflow()
        self.position_workflow = self.factory.build_position_analysis_workflow()
        self.query_workflow = self.factory.build_query_workflow()

    def invoke_resume_processing(self, pdf_content: str, filename: str) -> ResumeProcessState:
        """
        调用简历处理工作流

        Args:
            pdf_content: PDF文本内容
            filename: 文件名

        Returns:
            最终的状态对象，包含所有处理结果
        """
        logger.info(f"📄 启动简历处理工作流: {filename}")

        # 创建初始状态
        initial_state = create_resume_state(pdf_content, filename)

        # 调用工作流
        final_state = self.resume_workflow.invoke(initial_state)

        logger.info(f"✓ 简历处理完成: {final_state['message']}")
        return final_state

    def invoke_position_analysis(self, position_name: str, description: str) -> PositionAnalysisState:
        """
        调用岗位分析工作流

        Args:
            position_name: 岗位名称
            description: 岗位描述

        Returns:
            最终的状态对象，包含创建和分配结果
        """
        logger.info(f"🏢 启动岗位分析工作流: {position_name}")

        # 创建初始状态
        initial_state = create_position_state(position_name, description)

        # 调用工作流
        final_state = self.position_workflow.invoke(initial_state)

        logger.info(f"✓ 岗位分析完成: {final_state['message']}")
        return final_state

    def invoke_query(self, natural_language_query: str) -> QueryState:
        """
        调用自然语言查询工作流

        Args:
            natural_language_query: 自然语言查询

        Returns:
            最终的状态对象，包含查询结果和总结
        """
        logger.info(f"❓ 启动查询工作流: {natural_language_query}")

        # 创建初始状态
        initial_state = create_query_state(natural_language_query)

        # 调用工作流
        final_state = self.query_workflow.invoke(initial_state)

        logger.info(f"✓ 查询完成: {final_state['message']}")
        return final_state


# ==================== 工作流可视化支持 ====================

def visualize_resume_workflow():
    """生成简历处理工作流的可视化"""
    from langgraph.graph import StateGraph
    from agent_state import ResumeProcessState

    workflow = StateGraph(ResumeProcessState)
    workflow_obj = workflow.compile()

    # 获取ASCIIart表示
    ascii_art = workflow_obj.get_graph().draw_ascii()
    print(ascii_art)


def print_workflow_info():
    """打印所有工作流的信息"""
    info = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║               LangGraph 招聘系统工作流架构                        ║
    ╚══════════════════════════════════════════════════════════════════╝

    📄 工作流1: 简历处理流程
    ─────────────────────────────────────────────────────────────────
    START
      │
      ├─→ [extract_info]
      │     提取候选人结构化信息 (名字、年龄、技能等)
      │
      ├─→ [analyze_intention]
      │     分析是否有明确求职意向
      │
      ├─→ [evaluate_positions]
      │     对所有活跃岗位进行LLM评分
      │
      ├─→ [make_allocation_decision]
      │     根据意向和评分做出分配决策
      │     (三层逻辑处理)
      │
      ├─→ [save_to_database]
      │     保存候选人和所有评分记录到数据库
      │
      └─→ END

    🏢 工作流2: 岗位创建流程
    ─────────────────────────────────────────────────────────────────
    START
      │
      ├─→ [analyze_position]
      │     LLM分析岗位需求，提炼技能要求
      │
      ├─→ [create_position]
      │     保存岗位到数据库
      │
      ├─→ [reallocate_candidates]
      │     自动重新分配现有候选人
      │     - 有意向的候选人：检查是否匹配
      │     - 无意向的候选人：【不再重新分配】
      │
      └─→ END

    ❓ 工作流3: 自然语言查询流程
    ─────────────────────────────────────────────────────────────────
    START
      │
      ├─→ [understand_query]
      │     LLM理解查询意图，转化为结构化参数
      │
      ├─→ [execute_query]
      │     执行数据库查询
      │
      ├─→ [generate_summary]
      │     LLM生成人类可读的结果总结
      │
      └─→ END

    ═══════════════════════════════════════════════════════════════════
    核心优势：
    ✓ 状态管理清晰：每个工作流都有完整的状态对象
    ✓ 节点独立：每个节点是一个独立的可测试单元
    ✓ 错误处理：每个节点都有完整的错误处理逻辑
    ✓ 可观测性：详细的日志和状态跟踪
    ✓ 可扩展性：轻松添加新的节点或工作流
    ═══════════════════════════════════════════════════════════════════
    """
    print(info)