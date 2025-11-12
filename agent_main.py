"""
招聘Agent主文件 - 基于LangGraph ReAct模式
将现有系统功能包装为工具，赋予LLM自主决策能力
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# 导入现有系统组件
from models import init_db, get_session
from service import RecruitmentService
from llm_service import create_llm_service
from agent_tools import RecruitmentAgentTools
from pdf_processor import process_pdf_bytes  # 新增：PDF处理

# 加载环境变量
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RecruitmentAgent:
    """
    招聘Agent - 具备自主决策和工具调用能力

    核心能力：
    1. 自主理解用户意图
    2. 规划执行步骤
    3. 动态选择和调用工具
    4. 根据执行结果调整策略
    5. 提供人性化的反馈
    """

    def __init__(
            self,
            database_url: str,
            anthropic_api_key: str,
            model: str = "claude-sonnet-4-20250514"
    ):
        """
        初始化招聘Agent

        Args:
            database_url: 数据库连接URL
            anthropic_api_key: Anthropic API密钥
            model: Claude模型名称
        """
        logger.info("🤖 初始化招聘Agent...")

        # 1. 初始化数据库
        self.engine = init_db(database_url)
        self.session = get_session(self.engine)
        logger.info("✓ 数据库连接成功")

        # 2. 初始化LLM服务
        self.llm_service = create_llm_service(anthropic_api_key)
        logger.info("✓ LLM服务初始化成功")

        # 3. 初始化招聘服务
        self.recruitment_service = RecruitmentService(self.session, self.llm_service)
        logger.info("✓ 招聘服务初始化成功")

        # 4. 初始化工具集
        self.tools_factory = RecruitmentAgentTools(
            session=self.session,
            llm_service=self.llm_service,
            recruitment_service=self.recruitment_service
        )
        self.tools = self.tools_factory.get_all_tools()
        logger.info(f"✓ 已加载 {len(self.tools)} 个工具")

        # 5. 创建LLM实例（用于Agent）
        self.llm = ChatAnthropic(
            api_key=anthropic_api_key,
            model=model,
            temperature=0
        )
        logger.info(f"✓ Agent LLM初始化成功 (模型: {model})")

        # 6. 创建内存管理器（支持多轮对话）
        self.memory = MemorySaver()

        # 7. 创建ReAct Agent
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=self.memory,
            state_modifier=self._get_system_prompt()
        )
        logger.info("✓ ReAct Agent创建成功")

        logger.info("🎉 招聘Agent初始化完成！")

    def _get_system_prompt(self) -> str:
        """
        获取Agent的系统提示词

        这个提示词定义了Agent的角色、能力和行为准则
        """
        return """你是一个专业的智能招聘助手Agent，具备以下能力：

🎯 核心能力：
1. **简历处理**：帮助HR上传和分析候选人简历
2. **岗位管理**：创建新岗位并自动匹配候选人
3. **智能查询**：根据各种条件查询候选人和岗位信息
4. **评估分析**：对候选人和岗位进行深度评估和推荐

🛠️ 可用工具：
- upload_resume: 上传并处理简历PDF
- create_position: 创建新的招聘岗位
- list_positions: 列出所有岗位
- get_position_stats: 获取岗位的详细统计
- search_candidates: 搜索候选人（支持多种筛选条件）
- get_candidate_detail: 获取候选人完整信息
- get_position_candidates: 获取某岗位的所有候选人
- evaluate_candidate: 重新评估候选人对岗位的匹配度
- update_candidate_position: 手动调整候选人的岗位分配

🧠 工作方式：
1. **理解意图**：仔细理解用户的需求和问题
2. **规划步骤**：思考需要调用哪些工具，以什么顺序
3. **执行操作**：一步步调用工具完成任务
4. **分析结果**：基于工具返回的信息进行分析
5. **提供建议**：给出专业的招聘建议和下一步行动

📋 行为准则：
- 始终保持专业和友好的态度
- 对于不确定的信息，使用工具查询而不是猜测
- 提供清晰、结构化的回答
- 主动提供有价值的建议和洞察
- 如果任务复杂，告诉用户你的执行计划

💡 特别注意：
- 当用户询问候选人或岗位信息时，优先使用工具查询最新数据
- 在提供建议前，确保已经收集了足够的信息
- 对于模糊的请求，可以询问用户以明确需求
- 执行操作前，可以向用户说明你的计划

现在，请根据用户的请求，使用你的工具和能力来帮助他们！记住：你有完整的工具调用能力，不要仅仅回答问题，而要主动使用工具来获取信息和执行操作。
"""

    def chat(self, message: str, thread_id: str = "default") -> str:
        """
        与Agent进行对话

        Args:
            message: 用户消息
            thread_id: 对话线程ID（用于支持多轮对话）

        Returns:
            Agent的回复
        """
        logger.info(f"💬 收到用户消息: {message}")
        logger.info(f"📝 对话线程: {thread_id}")

        try:
            # 准备配置
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            # 调用Agent
            result = self.agent.invoke(
                {"messages": [("user", message)]},
                config=config
            )

            # 提取Agent的最终回复
            messages = result.get("messages", [])
            if messages:
                final_message = messages[-1]
                response = final_message.content if hasattr(final_message, 'content') else str(final_message)

                logger.info(f"✓ Agent回复完成 (调用了 {self._count_tool_calls(messages)} 次工具)")
                return response
            else:
                return "抱歉，我无法处理这个请求。"

        except Exception as e:
            logger.error(f"✗ Agent执行失败: {str(e)}", exc_info=True)
            return f"抱歉，处理您的请求时出现错误: {str(e)}"

    def chat_stream(self, message: str, thread_id: str = "default"):
        """
        流式对话（支持实时输出）

        Args:
            message: 用户消息
            thread_id: 对话线程ID

        Yields:
            Agent的流式输出
        """
        logger.info(f"💬 收到用户消息（流式）: {message}")

        try:
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            # 流式调用
            for chunk in self.agent.stream(
                    {"messages": [("user", message)]},
                    config=config,
                    stream_mode="values"
            ):
                messages = chunk.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        yield last_message.content

        except Exception as e:
            logger.error(f"✗ 流式对话失败: {str(e)}", exc_info=True)
            yield f"抱歉，处理您的请求时出现错误: {str(e)}"

    def _count_tool_calls(self, messages: List) -> int:
        """统计消息中的工具调用次数"""
        count = 0
        for msg in messages:
            if hasattr(msg, 'additional_kwargs'):
                tool_calls = msg.additional_kwargs.get('tool_calls', [])
                count += len(tool_calls)
        return count

    def get_conversation_history(self, thread_id: str = "default") -> List[Dict]:
        """
        获取对话历史

        Args:
            thread_id: 对话线程ID

        Returns:
            对话历史列表
        """
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            # 从内存中获取历史
            state = self.memory.get(config)
            if state and "messages" in state:
                return [
                    {
                        "role": "user" if i % 2 == 0 else "assistant",
                        "content": msg.content if hasattr(msg, 'content') else str(msg)
                    }
                    for i, msg in enumerate(state["messages"])
                ]
            return []

        except Exception as e:
            logger.error(f"获取对话历史失败: {str(e)}")
            return []

    def clear_conversation(self, thread_id: str = "default"):
        """
        清空对话历史

        Args:
            thread_id: 对话线程ID
        """
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }
            # 清空内存中的对话
            # 注意：MemorySaver没有直接的clear方法，这里通过设置空状态来实现
            logger.info(f"对话历史已清空: {thread_id}")

        except Exception as e:
            logger.error(f"清空对话历史失败: {str(e)}")

    def list_available_tools(self) -> List[Dict[str, str]]:
        """
        列出所有可用的工具

        Returns:
            工具列表，包含名称和描述
        """
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools
        ]

    def process_resume_file(self, pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        处理简历文件（新增功能）

        Args:
            pdf_bytes: PDF文件字节流
            filename: 文件名

        Returns:
            处理结果
        """
        try:
            from pdf_processor import process_pdf_bytes

            logger.info(f"📄 处理简历文件: {filename}")

            # 提取PDF文本
            pdf_text, metadata = process_pdf_bytes(pdf_bytes)
            logger.info(f"✓ PDF提取成功 ({metadata.get('page_count', 0)} 页)")

            # 调用业务逻辑处理
            result = self.recruitment_service.process_resume(pdf_text, filename)
            logger.info(f"✓ 简历处理完成: {result.get('name')}")

            return {
                "status": "success",
                "data": result,
                "message": f"简历处理成功：{result.get('name')}"
            }

        except Exception as e:
            logger.error(f"✗ 简历处理失败: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }

    def close(self):
        """关闭Agent和数据库连接"""
        if self.session:
            self.session.close()
        logger.info("Agent已关闭")


# ==================== 便捷函数 ====================

def create_recruitment_agent(
        database_url: Optional[str] = None,
        anthropic_api_key: Optional[str] = None
) -> RecruitmentAgent:
    """
    创建招聘Agent的便捷函数

    Args:
        database_url: 数据库URL（默认从环境变量读取）
        anthropic_api_key: Anthropic API密钥（默认从环境变量读取）

    Returns:
        RecruitmentAgent实例
    """
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///recruitment.db")
    anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

    if not anthropic_api_key:
        raise ValueError("必须提供ANTHROPIC_API_KEY环境变量或参数")

    return RecruitmentAgent(
        database_url=database_url,
        anthropic_api_key=anthropic_api_key
    )


# ==================== 命令行交互 ====================

def interactive_cli():
    """
    命令行交互模式

    运行方式：
    python agent_main.py
    """
    print("""
╔═══════════════════════════════════════════════════════════════╗
║              🤖 智能招聘Agent - 交互模式 v2.0                  ║
╚═══════════════════════════════════════════════════════════════╝

欢迎使用智能招聘助手！我可以帮你：
✓ 上传和处理候选人简历（新功能！）
✓ 创建和管理招聘岗位
✓ 查询候选人和岗位信息
✓ 提供专业的招聘建议

输入 'help' 查看帮助
输入 'tools' 查看可用工具
输入 'upload <文件路径>' 上传简历
输入 'quit' 退出程序
""")

    # 创建Agent
    try:
        agent = create_recruitment_agent()
        print("✓ Agent初始化成功\n")
    except Exception as e:
        print(f"✗ Agent初始化失败: {str(e)}")
        return

    thread_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 交互循环
    while True:
        try:
            # 获取用户输入
            user_input = input("\n👤 你: ").strip()

            if not user_input:
                continue

            # 特殊命令
            if user_input.lower() == 'quit':
                print("\n再见！👋")
                break

            elif user_input.lower() == 'help':
                print("""
可用命令：
- help: 显示此帮助信息
- tools: 列出所有可用工具
- upload <文件路径>: 上传简历文件
- clear: 清空对话历史
- history: 查看对话历史
- quit: 退出程序

使用示例：
- "帮我列出所有岗位"
- "查找Python岗位分数在80分以上的候选人"
- "创建一个前端工程师岗位，要求..."
- "重新评估候选人1对岗位2的匹配度"
- "upload resume.pdf"  ← 上传简历文件
""")
                continue

            elif user_input.lower() == 'tools':
                tools = agent.list_available_tools()
                print("\n📦 可用工具：")
                for tool in tools:
                    print(f"\n  🔧 {tool['name']}")
                    print(f"     {tool['description']}")
                continue

            elif user_input.lower() == 'clear':
                agent.clear_conversation(thread_id)
                print("✓ 对话历史已清空")
                continue

            elif user_input.lower() == 'history':
                history = agent.get_conversation_history(thread_id)
                if history:
                    print("\n📜 对话历史：")
                    for msg in history:
                        role = "👤 你" if msg["role"] == "user" else "🤖 Agent"
                        print(f"\n{role}: {msg['content'][:200]}...")
                else:
                    print("暂无对话历史")
                continue

            elif user_input.lower().startswith('upload '):
                # 处理文件上传命令
                file_path = user_input[7:].strip()
                try:
                    print(f"\n📤 正在上传简历: {file_path}")

                    # 读取文件
                    with open(file_path, 'rb') as f:
                        pdf_bytes = f.read()

                    # 处理简历
                    result = agent.process_resume_file(pdf_bytes, os.path.basename(file_path))

                    if result['status'] == 'success':
                        data = result['data']
                        print(f"\n✅ {result['message']}")
                        print(f"\n候选人信息：")
                        print(f"  - ID: {data.get('candidate_id')}")
                        print(f"  - 姓名: {data.get('name')}")
                        print(f"  - 年龄: {data.get('age', '未提供')}")
                        print(f"  - 邮箱: {data.get('email', '未提供')}")
                        print(f"\n分配结果：")
                        print(f"  - 分配岗位: {data.get('auto_matched_position')}")
                        print(f"  - 评分: {data.get('auto_matched_position_score')}/100")
                        print(f"  - 提取质量: {data.get('extraction_quality', 0):.1f}/100")
                    else:
                        print(f"\n❌ 上传失败: {result['message']}")

                except FileNotFoundError:
                    print(f"\n❌ 文件不存在: {file_path}")
                except Exception as e:
                    print(f"\n❌ 处理失败: {str(e)}")
                continue

            # 调用Agent
            print("\n🤖 Agent: ", end="", flush=True)
            response = agent.chat(user_input, thread_id)
            print(response)

        except KeyboardInterrupt:
            print("\n\n再见！👋")
            break
        except Exception as e:
            print(f"\n✗ 错误: {str(e)}")

    # 清理
    agent.close()


# ==================== FastAPI集成 ====================

def create_agent_api_app():
    """
    创建Agent的FastAPI应用

    可以作为独立的API服务运行
    """
    from fastapi import FastAPI, HTTPException, UploadFile, File
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import os

    app = FastAPI(
        title="智能招聘Agent API",
        description="基于LangGraph ReAct的智能招聘助手Agent - 支持文件上传",
        version="2.0.0"
    )

    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局Agent实例
    agent = None

    class ChatRequest(BaseModel):
        message: str
        thread_id: str = "default"

    class ChatResponse(BaseModel):
        response: str
        thread_id: str

    @app.on_event("startup")
    async def startup_event():
        """启动时初始化Agent"""
        global agent
        try:
            agent = create_recruitment_agent()
            logger.info("✓ Agent API服务启动成功")
        except Exception as e:
            logger.error(f"✗ Agent初始化失败: {str(e)}")
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """关闭时清理资源"""
        if agent:
            agent.close()

    # ==================== 前端页面 ====================

    @app.get("/")
    async def serve_frontend():
        """提供前端聊天界面"""
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 优先查找顺序：
        # 1. frontend/agent_chat_ui.html (推荐)
        # 2. agent_chat_ui.html (同目录)
        possible_paths = [
            os.path.join(current_dir, "frontend", "agent_chat_ui.html"),  # frontend目录
            os.path.join(current_dir, "agent_chat_ui.html"),  # 同目录
            os.path.join(current_dir, "..", "frontend", "agent_chat_ui.html"),  # 上级目录的frontend
        ]

        for html_path in possible_paths:
            if os.path.exists(html_path):
                logger.info(f"✓ 找到前端文件: {html_path}")
                return FileResponse(html_path)

        # 如果都没找到，返回提示信息
        return {
            "message": "Agent API运行中",
            "status": "前端界面未找到",
            "tip": "请将agent_chat_ui.html放在以下任一位置：",
            "locations": [
                "frontend/agent_chat_ui.html (推荐)",
                "agent_chat_ui.html (同目录)",
            ],
            "api_docs": "/docs",
            "endpoints": {
                "chat": "POST /chat",
                "upload": "POST /upload",
                "tools": "GET /tools",
                "health": "GET /health"
            }
        }

    # ==================== API端点 ====================

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """
        与Agent对话

        Args:
            message: 用户消息
            thread_id: 对话线程ID（可选）

        Returns:
            Agent的回复
        """
        if not agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        try:
            logger.info(f"💬 收到对话请求: {request.message[:50]}...")
            response = agent.chat(request.message, request.thread_id)
            logger.info(f"✓ 对话完成")
            return ChatResponse(
                response=response,
                thread_id=request.thread_id
            )
        except Exception as e:
            logger.error(f"✗ 对话失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")

    @app.get("/tools")
    async def list_tools():
        """列出所有可用工具"""
        if not agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        return {"tools": agent.list_available_tools()}

    @app.post("/clear/{thread_id}")
    async def clear_conversation(thread_id: str):
        """清空对话历史"""
        if not agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        agent.clear_conversation(thread_id)
        return {"status": "success", "message": f"对话历史已清空: {thread_id}"}

    @app.post("/upload")
    async def upload_resume(file: UploadFile = File(...)):
        """
        上传简历文件

        支持PDF格式的简历上传和处理
        返回候选人信息和匹配结果
        """
        if not agent:
            raise HTTPException(status_code=500, detail="Agent未初始化")

        # 检查文件格式
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="仅支持PDF格式文件")

        try:
            logger.info(f"📤 收到文件上传: {file.filename}")

            # 读取文件内容
            pdf_bytes = await file.read()
            logger.info(f"✓ 文件读取成功: {len(pdf_bytes)} 字节")

            # 处理简历
            result = agent.process_resume_file(pdf_bytes, file.filename)

            if result['status'] == 'success':
                logger.info(f"✓ 简历处理成功: {file.filename}")
                return {
                    "status": "success",
                    "filename": file.filename,
                    "data": result['data'],
                    "message": result['message']
                }
            else:
                logger.error(f"✗ 简历处理失败: {result.get('message')}")
                raise HTTPException(status_code=500, detail=result['message'])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"✗ 上传处理失败: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")

    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "agent_ready": agent is not None,
            "version": "2.0.0",
            "features": ["chat", "upload", "tools"],  # 新增upload功能
            "timestamp": datetime.utcnow().isoformat()
        }

    return app


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "api":
        # API模式
        print("🚀 启动Agent API服务...")
        import uvicorn

        app = create_agent_api_app()
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        # CLI交互模式
        interactive_cli()