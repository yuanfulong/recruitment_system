# 智能招聘助手系统 v1.0 - LangGraph版本

基于LangGraph多工作流编排的智能简历分析和岗位匹配系统。该系统使用Claude LLM进行结构化信息提取、求职意向分析、岗位智能匹配和自然语言查询处理。

## 🎯 核心特性

### 智能简历处理
- **PDF智能解析**：使用pdfplumber提取简历文本
- **结构化信息提取**：通过Claude LLM提取姓名、技能、工作经历、教育背景等
- **提取质量评分**：自动评估提取内容的完整度（0-100分）
- **候选人版本控制**：保存每次上传的简历版本

### 多维度岗位匹配
- **绝对评分制**：统一60分基线，0-100分四级评价体系（A/B/C/D）
- **LLM深度评估**：基于岗位需求进行详细评分，包含理由和差距分析
- **动态重新分配**：新增岗位自动触发匹配评估
- **求职意向三层处理**：
  1. 有明确意向 + 岗位存在 → 岗位匹配后不再改动
  2. 有明确意向 + 岗位不存在 → 临时分配最优，若期待的岗位创建，成为状态1，否则随着状态3不断重新评估
  3. 无明确意向 → 自动分配最优，新岗位时重新评估

### LangGraph工作流编排
系统包含3个完整的LangGraph工作流，支持状态管理、错误处理和可观测性：

1. **简历处理工作流** - 7步处理流程
2. **岗位分析工作流** - 3步创建和分配流程
3. **自然语言查询工作流** - 3步查询处理流程

### 完整的审计追踪
- **操作日志**：记录所有系统操作（创建、更新、删除）
- **分配历史**：追踪每次岗位分配的变化和原因
- **版本历史**：保存候选人简历版本

## 📋 系统架构

### 文件结构
```
recruitment_system/
├── main_langgraph.py          # FastAPI主应用 + 所有API端点
├── llm_service.py             # Claude LLM集成服务
├── service.py                 # 核心业务逻辑
├── models.py                  # SQLAlchemy数据库模型
├── schemas.py                 # Pydantic数据验证模型
├── pdf_processor.py           # PDF文本提取模块
├── agent_workflows.py         # LangGraph工作流定义
├── agent_nodes.py             # 工作流节点实现
├── agent_state.py             # 工作流状态定义
├── requirements.txt           # Python依赖
├── .env                       # 环境配置（需创建）
├── .env.example               # 环境配置示例
├── Dockerfile                 # Docker镜像构建
├── docker-compose.yml         # Docker服务编排
├── start.sh                   # 启动脚本
├── index.html                 # 前端界面（可选）
└── recruitment.db             # SQLite数据库（本地开发）
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
└── 统计字段

candidate_position_match       # 匹配评分表
├── match_id (PK)
├── candidate_id (FK)
├── position_id (FK)
├── overall_score (0-100)
└── grade (A/B/C/D)

position_allocation_history    # 分配历史
├── history_id (PK)
├── 旧岗位、新岗位、分数变化
└── 触发事件类型

audit_log                       # 审计日志
├── 操作者、操作类型
└── 详细信息

candidate_version              # 候选人版本控制
├── 每次上传的快照
└── 上传时间
```

## 🚀 快速开始

### 前置要求
- Python 3.9+
- 有效的Claude API密钥
- PostgreSQL数据库（可选，默认SQLite，测试开发也是以本地数据库sqlite版本开发的，PostgreSQL数据库的代码以开发并且以注释形式表示，不过从未验证过）

### 1. 环境准备

```bash
# 克隆或下载项目
cd recruitment_system

# 复制环境文件
cp .env.example .env

# 编辑 .env 文件配置
nano .env
# 需要配置：
# - DATABASE_URL: 数据库连接字符串
# - ANTHROPIC_API_KEY: Claude API密钥
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 启动应用

```bash
# 方式1：使用启动脚本（推荐）
chmod +x start.sh
./start.sh

# 方式2：手动启动
python main_langgraph.py

# 方式3：使用Uvicorn
uvicorn main_langgraph:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问应用

```
🌐 API文档（Swagger UI）: http://localhost:8000/docs
📊 健康检查: http://localhost:8000/api/health
🎨 前端界面（如有）: http://localhost:8000/ui
```

## 📡 API 使用指南

### 1. 健康检查
```bash
curl http://localhost:8000/api/health
```

**响应示例**：
```json
{
  "status": "healthy",
  "database": "connected",
  "positions": 3,
  "candidates": 15,
  "system_ready": true
}
```

### 2. 创建岗位
```bash
curl -X POST "http://localhost:8000/api/positions" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Python后端工程师",
    "description": "负责API开发、数据库设计、系统架构...",
    "required_skills": ["Python 3年+", "Web框架", "SQL"],
    "nice_to_have": ["分布式系统", "开源贡献"]
  }'
```

**响应示例**：
```json
{
  "status": "success",
  "position_id": 1,
  "position_name": "Python后端工程师",
  "reallocation_result": {
    "total_candidates_scanned": 0,
    "candidates_reallocated": 0,
    "changes": []
  }
}
```

### 3. 上传简历
```bash
curl -X POST "http://localhost:8000/api/candidates/upload" \
  -F "file=@resume.pdf"
```

**响应示例**：
```json
{
  "status": "success",
  "candidate_id": 1,
  "name": "张三",
  "age": 28,
  "email": "zhangsan@example.com",
  "auto_matched_position": "Python后端工程师",
  "auto_matched_position_score": 85,
  "is_position_locked": true,
  "no_matched_position": false,
  "extraction_quality": 92.5
}
```

### 4. 获取候选人详情
```bash
curl "http://localhost:8000/api/candidates/1"
```

**响应示例**：
```json
{
  "candidate_id": 1,
  "name": "张三",
  "age": 28,
  "auto_matched_position": "Python后端工程师",
  "auto_matched_position_score": 85,
  "is_position_locked": true,
  "positions": [
    {
      "position_name": "Python后端工程师",
      "score": 85,
      "grade": "B",
      "evaluation_reason": "5年Python经验，框架熟悉，缺少分布式经验"
    }
  ]
}
```

### 5. 列表查询候选人
```bash
curl "http://localhost:8000/api/candidates?skip=0&limit=20"
```

### 6. 查看岗位的候选人
```bash
curl "http://localhost:8000/api/positions/1/candidates?min_grade=C"
```

**响应示例**：
```json
{
  "position_id": 1,
  "position_name": "Python后端工程师",
  "total_candidates": 3,
  "candidates": [
    {
      "candidate_id": 1,
      "name": "张三",
      "score": 85,
      "grade": "B",
      "email": "zhangsan@example.com"
    }
  ]
}
```

### 7. 自然语言查询
```bash
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "找出Python岗位的所有B级候选人"}'
```

**响应示例**：
```json
{
  "query": "找出Python岗位的所有B级候选人",
  "total": 2,
  "results": [
    {
      "candidate_name": "张三",
      "score": 85,
      "grade": "B",
      "email": "zhangsan@example.com"
    }
  ],
  "summary": "Python开发岗位目前有2个B级候选人..."
}
```

## 🔄 三大核心工作流

### 工作流1：简历处理工作流（ResumeProcessingWorkflow）

```
START
  ↓
[1] extract_info - 提取候选人结构化信息
    ├─ PDF → 文本
    ├─ 信息抽取 (Claude LLM)
    ├─ 结构化输出 (JSON Schema)
    └─ 质量评分
  ↓
[2] analyze_intention - 分析求职意向
    ├─ 是否有明确意向？
    ├─ 意向岗位是什么？
    └─ 信息来源在哪？
  ↓
[3] evaluate_positions - 对所有岗位评分
    ├─ 遍历所有活跃岗位
    ├─ LLM逐一评分
    ├─ 输出：0-100分 + A/B/C/D等级
    └─ 并发处理提高性能
  ↓
[4] make_allocation_decision - 做出分配决策
    ├─ 情况1：有意向 + 岗位存在
    │  └─ is_locked=TRUE (永不改)
    ├─ 情况2：有意向 + 岗位不存在
    │  └─ no_matched=TRUE (等待)
    └─ 情况3：无意向
       └─ 自动分配最优
  ↓
[5] save_to_database - 保存数据
    ├─ Candidate记录
    ├─ CandidatePositionMatch评分
    ├─ CandidateVersion版本
    └─ AuditLog操作记录
  ↓
END (返回processing_result)
```

**状态输出**：`ResumeProcessState`包含：
- extracted_info：候选人信息
- job_intention：求职意向
- evaluations：所有岗位评分
- allocation_decision：最终分配
- candidate_id：数据库ID

### 工作流2：岗位分析工作流（PositionAnalysisWorkflow）

```
START
  ↓
[1] analyze_position - 分析岗位需求
    ├─ LLM读取岗位描述
    ├─ 提炼核心需求技能
    ├─ 识别加分项（nice_to_have）
    └─ 生成评分指南（evaluation_prompt）
  ↓
[2] create_position - 创建岗位
    └─ 插入Position表 → position_id
  ↓
[3] reallocate_candidates - 自动重新分配
    ├─ 扫描所有候选人
    ├─ 【情况1】有意向 + 已锁定 → SKIP
    ├─ 【情况2】有意向 + 未锁定 + no_matched
    │  ├─ LLM判断是否匹配
    │  ├─ YES → 更新 + 锁定 + 记录变化
    │  └─ NO → SKIP
    └─ 【情况3】无意向
       ├─ 计算新岗位分数
       ├─ 比较旧分数
       ├─ 更高则更新
       └─ 记录变化
  ↓
END (返回reallocation_result)
```

**状态输出**：`PositionAnalysisState`包含：
- position_id：创建的岗位ID
- reallocation_changes：所有分配变化
- summary：变化统计

### 工作流3：自然语言查询工作流（QueryWorkflow）

```
START
  ↓
[1] understand_query - 理解查询意图
    ├─ LLM分析查询内容
    ├─ 识别查询类型
    │  ├─ position_candidates：某岗位的候选人
    │  ├─ candidate_positions：某候选人的岗位评分
    │  └─ statistics：统计查询
    └─ 转化为结构化参数
  ↓
[2] execute_query - 执行数据库查询
    ├─ 根据params类型执行不同查询
    ├─ 支持分页和过滤
    └─ 返回结果集
  ↓
[3] generate_summary - 生成结果总结
    ├─ LLM读取查询结果
    ├─ 生成人类可读总结
    └─ 提供推荐建议
  ↓
END (返回query_result)
```

**状态输出**：`QueryState`包含：
- query_type：识别的查询类型
- query_results：查询结果数据
- summary：LLM生成的总结

## 🛠️ Docker部署

### 使用Docker Compose（推荐）

```bash
# 1. 编辑 .env 配置文件
nano .env

# 2. 启动所有服务（PostgreSQL + 应用）
docker-compose up -d

# 3. 查看日志
docker-compose logs -f app

# 4. 停止服务
docker-compose down
```

### 单独使用Docker

```bash
# 1. 构建镜像
docker build -t recruitment-system:1.0 .

# 2. 运行容器（需要外部PostgreSQL）
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/db" \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  --name recruitment-app \
  recruitment-system:1.0

# 3. 查看日志
docker logs -f recruitment-app
```

## 🔐 环境变量配置

创建 `.env` 文件：

```env
# 数据库配置
# SQLite（本地开发，无需外部数据库）
DATABASE_URL=sqlite:///recruitment.db

# 或PostgreSQL（生产环境）
# DATABASE_URL=postgresql://user:password@localhost:5432/recruitment_db

# Claude API配置
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# 应用配置
ENV=development
DEBUG=True
LOG_LEVEL=INFO
PORT=8000
HOST=0.0.0.0
```

### 获取API密钥

1. 访问 https://console.anthropic.com
2. 创建或选择项目
3. 生成API密钥
4. 复制到 `.env` 文件

## 📊 性能优化建议

### 1. 数据库优化
```python
# 为常用查询字段添加索引
# 在models.py中添加
name = Column(String(100), nullable=False, index=True)
auto_matched_position = Column(String(100), nullable=True, index=True)
has_explicit_position = Column(Boolean, default=False, index=True)
```

### 2. LLM调用优化
- 实现请求缓存避免重复评分
- 并发处理多个岗位评分
- 设置API超时和重试机制

### 3. 异步处理
- 使用Celery处理大量简历上传
- 后台任务队列处理重新分配
- 异步日志写入

## 🐛 常见问题

### Q1: 系统启动报"岗位库为空"错误
**A**: 这是正常的。系统需要至少一个岗位才能处理简历。
```bash
# 通过API创建第一个岗位
curl -X POST "http://localhost:8000/api/positions" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试岗位","description":"测试描述"}'
```

### Q2: PDF上传失败，提示"无法解析PDF"
**A**: 检查：
1. PDF文件是否损坏
2. PDF文件大小是否过大（>50MB）
3. PDF是否为真实文本，而不是扫描图片

### Q3: Claude API调用超时
**A**: 解决方案：
1. 检查网络连接
2. 检查API密钥是否有效
3. 确认API配额充足
4. 增加超时时间

### Q4: 数据库连接失败
**A**: 检查清单：
```bash
# PostgreSQL连接
psql postgresql://user:password@localhost:5432/recruitment_db

# 或查看连接字符串
echo $DATABASE_URL

# SQLite查看文件
ls -lah recruitment.db
```

### Q5: 同一个候选人上传多份简历会怎样？
**A**: 系统会：
1. 创建新的Candidate记录（不同的candidate_id）
2. 保存到CandidateVersion表记录版本历史
3. 重新评估所有岗位

### Q6: 如何重置所有数据？
**A**: 
```bash
# 方式1：删除数据库文件（SQLite）
rm recruitment.db

# 方式2：重新创建数据库
python -c "from models import init_db; init_db('sqlite:///recruitment.db')"

# 方式3：清空PostgreSQL数据库
dropdb recruitment_db
createdb recruitment_db
```

## 📈 系统扩展

### 后续开发方向

- [ ] **集成消息队列** - 使用Celery+Redis处理异步任务
- [ ] **缓存层** - Redis缓存热点查询和LLM结果
- [ ] **向量数据库** - pgvector支持向量相似度搜索
- [ ] **高级分析** - 候选人潜力评估、薪资预测
- [ ] **多语言支持** - 支持中英文混合简历
- [ ] **背景调查集成** - 与第三方API集成
- [ ] **推荐系统** - 智能推荐最优匹配
- [ ] **报表导出** - 生成招聘数据报告
- [ ] **权限管理** - 添加用户和角色系统
- [ ] **前端完善** - React/Vue完整前端界面

### 模块扩展示例

```python
# 添加新的LLM方法
class LLMService:
    def estimate_candidate_salary(self, candidate_info):
        """估计候选人薪资范围"""
        pass
    
    def generate_interview_questions(self, position, candidate):
        """为特定候选人生成面试题"""
        pass

# 添加新的工作流
class AdvancedWorkflows:
    def build_matching_workflow(self):
        """智能匹配工作流"""
        pass
    
    def build_offer_workflow(self):
        """offer生成工作流"""
        pass
```

## 📚 项目学习路径

推荐按此顺序阅读代码以理解系统设计：

1. **models.py** - 了解数据结构和关键字段
2. **schemas.py** - 了解API数据格式和验证
3. **agent_state.py** - 了解LangGraph状态定义
4. **agent_workflows.py** - 了解工作流编排
5. **agent_nodes.py** - 了解节点实现细节
6. **llm_service.py** - 了解LLM集成
7. **service.py** - 了解业务逻辑
8. **main_langgraph.py** - 了解API端点

## 🤝 贡献指南

欢迎提交问题和改进建议！

## 📄 许可证

MIT License - 可自由使用、修改和分发

## 📞 技术支持

- 📖 **文档**：查看README.md和代码注释
- 🐛 **问题排查**：查看常见问题部分
- 📊 **API文档**：http://localhost:8000/docs
- 🔗 **Claude文档**：https://docs.anthropic.com
- 📚 **LangGraph文档**：https://langchain-ai.github.io/langgraph

---

**版本**：1.0.0 LangGraph Edition  
**最后更新**：2025年11月10日  
**状态**：✅ 生产就绪  
**Python版本**：3.9+  (开发环境为3.11)
**依赖**：LangGraph 0.2.76 + LangChain 0.3.25 + FastAPI