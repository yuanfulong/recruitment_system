# 智能招聘Agent系统 v2.0 - 对话式招聘助手

基于LangGraph ReAct模式的智能招聘管理系统。该系统通过自然语言对话完成简历处理、岗位管理、候选人匹配等全流程招聘工作，同时提供传统API接口和Web聊天界面。

## 🎯 核心特性

### 🤖 Agent智能决策
- **自然语言交互**：通过对话完成所有招聘操作，无需记忆API端点
- **自主规划执行**：Agent自动理解意图、规划步骤、选择工具
- **多轮对话支持**：记住对话上下文，支持连续交互
- **智能建议**：提供专业的招聘分析和决策建议

### 📋 完整CRUD能力
- **简历处理**：上传PDF简历、自动提取信息、智能评分匹配
- **岗位管理**：创建岗位、分析要求、自动重新分配候选人
- **候选人管理**：查询、筛选、评估、调整岗位分配
- **数据分析**：实时统计、多维度查询、智能推荐

### 🛠️ 9个Agent工具
1. **upload_resume** - 上传并处理简历
2. **create_position** - 创建新岗位
3. **list_positions** - 列出所有岗位
4. **get_position_stats** - 获取岗位统计
5. **search_candidates** - 搜索候选人（支持多维度筛选）
6. **get_candidate_detail** - 获取候选人详情
7. **get_position_candidates** - 查看岗位候选人列表
8. **evaluate_candidate** - 重新评估匹配度
9. **update_candidate_position** - 调整岗位分配

### 🎨 多种使用方式
- **Web聊天界面**：美观的对话式交互界面
- **CLI命令行**：终端交互模式，支持文件上传
- **REST API**：完整的API接口，支持程序化调用
- **混合使用**：可与原工作流系统并存使用

## 📊 系统架构

### 双系统架构

```
┌─────────────────────────────────────────────────────┐
│  工作流系统 (main_langgraph.py) - 端口8000          │
│  ├─ 可视化Web界面                                    │
│  ├─ 预定义工作流                                    │
│  └─ 适合：批量操作、日常HR工作                       │
└─────────────────────────────────────────────────────┘
                      ↕ (共享数据库)
┌─────────────────────────────────────────────────────┐
│  Agent系统 (agent_main.py) - 端口8001               │
│  ├─ 对话式聊天界面                                   │
│  ├─ 智能决策引擎                                    │
│  └─ 适合：复杂查询、智能分析、灵活操作               │
└─────────────────────────────────────────────────────┘
```

### 文件结构

```
recruitment_system/
├── agent_main.py              # Agent主程序（新增）⭐
├── agent_tools.py             # Agent工具定义（新增）⭐
├── agent_state.py             # 工作流状态定义
├── agent_nodes.py             # 工作流节点实现
├── agent_workflows.py         # LangGraph工作流定义
│
├── main_langgraph.py          # 工作流系统主应用
├── llm_service.py             # Claude LLM集成服务
├── service.py                 # 核心业务逻辑
├── models.py                  # SQLAlchemy数据库模型
├── schemas.py                 # Pydantic数据验证模型
├── pdf_processor.py           # PDF文本提取模块
│
├── frontend/                  # 前端文件（推荐）⭐
│   ├── agent_chat_ui.html    # Agent聊天界面（新增）
│   └── index.html            # 工作流界面（原有）
│
├── requirements.txt           # Python依赖
├── .env                       # 环境配置（需创建）
├── .env.example              # 环境配置示例
└── recruitment.db            # SQLite数据库（本地开发）
```

### 数据库架构

```
candidates                      # 候选人表
├── candidate_id (PK)
├── name, age, email, phone
├── has_explicit_position      # 是否有明确意向
├── explicit_position          # 具体意向岗位
├── is_position_locked         # 岗位是否锁定
├── no_matched_position        # 是否意向岗位不存在
├── auto_matched_position      # 系统分配岗位
└── auto_matched_position_score

positions                       # 岗位表
├── position_id (PK)
├── name, description
├── required_skills (JSON)
├── nice_to_have (JSON)
├── evaluation_prompt
└── 统计字段（实时查询）

candidate_position_match       # 匹配评分表
├── match_id (PK)
├── candidate_id (FK)
├── position_id (FK)
├── overall_score (0-100)
└── grade (A/B/C/D)

position_allocation_history    # 分配历史
audit_log                       # 审计日志
candidate_version              # 候选人版本控制
```

## 🚀 快速开始

### 前置要求

- Python 3.9+ （开发环境：3.11）
- 有效的Claude API密钥
- SQLite（默认）或PostgreSQL

### 1. 环境准备

```bash
# 克隆项目
cd recruitment_system

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置：
# DATABASE_URL=sqlite:///recruitment.db
# ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 2. 启动Agent系统

#### 方式1：Web界面模式（推荐）

```bash
# 启动Agent API服务
python agent_main.py api

# 浏览器访问
http://localhost:8001/
```

#### 方式2：命令行交互模式

```bash
# 启动CLI模式
python agent_main.py

# 开始对话
👤 你: 列出所有岗位
🤖 Agent: [显示结果...]

# 上传简历
👤 你: upload resume.pdf
```

#### 方式3：同时运行两套系统

```bash
# Terminal 1: 工作流系统
python main_langgraph.py
# → http://localhost:8000/

# Terminal 2: Agent系统
python agent_main.py api
# → http://localhost:8001/
```

### 3. 首次使用

```bash
# 1. 创建第一个岗位（必须）
# 在Agent界面输入：
👤 你: 创建一个Python后端工程师岗位，要求3年以上经验，熟悉Django和FastAPI

# 2. 上传简历
# 点击 📎 按钮选择PDF文件，或CLI中：
👤 你: upload candidate_resume.pdf

# 3. 查询匹配
👤 你: Python岗位有哪些候选人？
```

## 💬 Agent使用指南

### 对话示例

#### 示例1：查询信息

```
👤 你: 列出所有岗位
🤖 Agent: 共找到 9 个岗位：
         1. Python后端工程师 (3个候选人)
         2. Java后端开发 (3个候选人)
         ...

👤 你: Python岗位有多少人？
🤖 Agent: Python后端工程师岗位目前有3个候选人...

👤 你: 给我看分数最高的
🤖 Agent: 根据评分，张三（85分）是Python岗位评分最高的候选人...
```

#### 示例2：复杂分析

```
👤 你: 帮我分析一下Python岗位的候选人质量，给我一些招聘建议
🤖 Agent: [自动调用多个工具]
         1. 查询岗位信息
         2. 获取所有候选人
         3. 分析评分分布
         4. 生成专业建议

         分析结果：...
         招聘建议：...
```

#### 示例3：上传和查询

```
👤 你: upload candidate_resume.pdf
🤖 Agent: ✅ 简历处理成功！
         候选人：李四
         分配岗位：Python后端工程师（78分）

👤 你: 这个候选人的详细信息
🤖 Agent: [显示完整信息]

👤 你: 他适合哪些岗位？
🤖 Agent: [展示所有岗位的评分]
```

### CLI命令

```bash
help        # 查看帮助
tools       # 列出所有工具
upload <文件路径>  # 上传简历
clear       # 清空对话历史
quit        # 退出程序
```

### Web界面功能

- **📎 文件上传**：点击按钮上传PDF简历
- **💬 对话交互**：输入框发送消息
- **⚡ 快捷按钮**：常用操作一键触发
- **🔄 清空对话**：清除历史记录
- **❓ 帮助说明**：查看使用指南

## 🔧 API接口文档

### Agent API（端口8001）

#### 1. 对话接口

```bash
curl -X POST "http://localhost:8001/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "列出所有岗位",
    "thread_id": "user_session_1"
  }'
```

**响应**：
```json
{
  "response": "共找到9个岗位：\n1. Python后端工程师...",
  "thread_id": "user_session_1"
}
```

#### 2. 上传简历

```bash
curl -X POST "http://localhost:8001/upload" \
  -F "file=@resume.pdf"
```

**响应**：
```json
{
  "status": "success",
  "filename": "resume.pdf",
  "data": {
    "candidate_id": 4,
    "name": "张三",
    "auto_matched_position": "Python后端工程师",
    "auto_matched_position_score": 85
  },
  "message": "简历处理成功：张三"
}
```

#### 3. 查看工具列表

```bash
curl "http://localhost:8001/tools"
```

#### 4. 健康检查

```bash
curl "http://localhost:8001/health"
```

**响应**：
```json
{
  "status": "healthy",
  "agent_ready": true,
  "version": "2.0.0",
  "features": ["chat", "upload", "tools"]
}
```

### 工作流API（端口8000）

保持原有API不变，详见工作流系统文档。

## 🎯 使用场景对比

| 场景 | 推荐系统 | 原因 |
|-----|---------|------|
| 快速查询信息 | Agent (8001) | 自然语言，无需记API |
| 单个简历处理 | Agent (8001) | 对话式，更便捷 |
| 批量上传100份简历 | 工作流 (8000) | Web界面，批量操作 |
| 复杂数据分析 | Agent (8001) | 智能决策，深度分析 |
| 查看数据表格 | 工作流 (8000) | 可视化界面 |
| 获取招聘建议 | Agent (8001) | 智能分析能力 |
| 日常HR操作 | 两者都可 | 根据个人习惯 |

## 🔄 Agent工作原理

### ReAct模式

```
用户输入：帮我找Python岗位分数最高的候选人

Agent思考过程：
┌─────────────────────────────────────┐
│ Step 1: 理解意图                     │
│ 需要：1) 找到Python岗位              │
│       2) 获取该岗位候选人            │
│       3) 按分数排序                  │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Step 2: 选择工具                     │
│ 决定使用：get_position_candidates    │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Step 3: 执行工具                     │
│ 调用工具并获取数据                    │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Step 4: 分析结果                     │
│ 找出分数最高的候选人                  │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│ Step 5: 生成回答                     │
│ 格式化输出，包含详细信息              │
└─────────────────────────────────────┘
```

### 工具自动选择

Agent会根据任务自动选择和组合工具：

```python
# 简单查询 → 1个工具
"列出岗位" → list_positions()

# 中等复杂 → 2-3个工具
"Python岗位有多少人？" → 
    list_positions() → get_position_candidates()

# 复杂任务 → 5+个工具
"给我Python岗位最好的3个候选人的详细信息" →
    list_positions() → get_position_candidates() →
    排序 → get_candidate_detail() × 3
```

## 🛠️ 开发指南

### 添加新工具

在 `agent_tools.py` 中：

```python
def create_my_new_tool(self):
    """创建新工具"""
    
    @tool
    def my_new_tool(param: str) -> str:
        """工具描述，Agent会看到这个"""
        # 调用现有业务逻辑
        result = self.service.some_method(param)
        return format_result(result)
    
    return my_new_tool

# 在 get_all_tools() 中注册
def get_all_tools(self):
    tools = [
        # ... 现有工具
        self.create_my_new_tool(),  # 新工具
    ]
    return tools
```

### 自定义Agent行为

修改 `agent_main.py` 中的 `_get_system_prompt()` 方法来调整Agent的行为风格。

### 前端定制

编辑 `frontend/agent_chat_ui.html`：

```html
<!-- 修改主题色 -->
<style>
    background: linear-gradient(135deg, #your-color1 0%, #your-color2 100%);
</style>

<!-- 添加新的快捷按钮 -->
<button class="quick-action" onclick="sendQuickMessage('你的消息')">
    🎯 你的按钮
</button>
```

## 📈 性能说明

| 操作类型 | 响应时间 | 说明 |
|---------|---------|------|
| 简单查询 (1-2个工具) | 1-2秒 | 如列出岗位 |
| 中等复杂 (3-5个工具) | 3-5秒 | 如查询并分析 |
| 复杂任务 (5+个工具) | 5-10秒 | 如深度分析报告 |
| PDF上传 | 5-15秒 | 取决于简历复杂度 |

## 🐛 常见问题

### Q1: Agent Web界面打开但无法对话？

**A**: 检查后端日志，确保Agent API正在运行：
```bash
python agent_main.py api
# 应该看到："✓ Agent API服务启动成功"
```

### Q2: 上传PDF失败？

**A**: 
1. 确保文件是PDF格式
2. 文件大小 < 10MB
3. 检查后端日志查看详细错误

### Q3: Agent说找不到岗位？

**A**: 需要先创建至少一个岗位：
```
👤 你: 创建一个Python工程师岗位，要求3年经验
```

### Q4: 如何重置数据库？

**A**: 
```bash
rm recruitment.db
python agent_main.py api
# 会自动创建新数据库
```

### Q5: 能同时使用Agent和工作流系统吗？

**A**: 可以！两个系统共享同一数据库，可以同时运行：
```bash
# Terminal 1
python main_langgraph.py  # 端口8000

# Terminal 2  
python agent_main.py api  # 端口8001
```

## 📊 诊断工具

### 数据库诊断

```bash
python diagnose_db.py
```

输出：
- 候选人数量和详情
- 岗位数量和统计
- 匹配记录
- 数据一致性检查

### 修复统计字段

```bash
python fix_statistics.py
```

## 🔐 安全建议

1. **API密钥管理**：不要提交 `.env` 到Git
2. **访问控制**：生产环境添加身份验证
3. **CORS配置**：限制允许的来源域名
4. **数据备份**：定期备份数据库文件

## 📚 技术栈

- **LLM**: Claude Sonnet 4 (Anthropic)
- **Agent框架**: LangGraph 0.2.76
- **Web框架**: FastAPI
- **数据库**: SQLAlchemy + SQLite/PostgreSQL
- **PDF处理**: pdfplumber
- **前端**: 原生HTML/CSS/JavaScript

## 🎓 学习资源

- [LangGraph文档](https://langchain-ai.github.io/langgraph)
- [Anthropic Claude API](https://docs.anthropic.com)
- [FastAPI文档](https://fastapi.tiangolo.com)

## 📄 许可证

MIT License - 可自由使用、修改和分发

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📞 技术支持

- 📖 完整文档：查看项目中的 `*.md` 文档
- 🐛 问题排查：查看 `DEBUG_500_ERROR.md`
- 🔧 前端配置：查看 `FRONTEND_DIRECTORY_GUIDE.md`
- 🏗️ 架构优化：查看 `ARCHITECTURE_OPTIMIZATION.md`

---

**版本**: v2.0.0 Agent Edition  
**发布日期**: 2025-11-12  
**状态**: ✅ 生产就绪  
**Python版本**: 3.9+ (开发环境：3.11)  
**核心依赖**: LangGraph 0.2.76 + LangChain 0.3.25 + Anthropic Claude  

**🚀 立即开始**: `python agent_main.py api` → 访问 `http://localhost:8001/`