# 智能招聘助手系统 - 代码生成完成总结

## 📁 项目结构

```
recruitment_system/
├── models.py                  # SQLAlchemy数据库模型定义
├── schemas.py                 # Pydantic数据验证模型
├── llm_service.py            # LLM集成（Claude API）
├── pdf_processor.py          # PDF处理模块
├── service.py                # 核心业务逻辑
├── main.py                   # FastAPI主应用 + 所有API端点
├── requirements.txt          # Python依赖
├── .env                      # 环境配置文件
├── .env.example              # 环境配置示例
├── Dockerfile                # Docker镜像
├── docker-compose.yml        # Docker Compose编排
├── start.sh                  # 启动脚本
└── README.md                 # 项目文档
```

## 🚀 核心模块说明

### 1. models.py - 数据库模型
**职责**：定义所有数据表结构
- `Candidate`：候选人表
- `Position`：岗位表
- `CandidatePositionMatch`：匹配记录表
- `PositionAllocationHistory`：分配历史表
- `AuditLog`：审计日志表
- `CandidateVersion`：版本历史表

**关键字段**：
- `has_explicit_position`：是否有明确求职意向
- `is_position_locked`：岗位是否被锁定
- `no_matched_position`：是否因意向岗位不存在
- `auto_matched_position`：系统分配的岗位

### 2. schemas.py - 数据验证
**职责**：定义所有API请求/响应的数据结构
- 请求验证：`PositionCreateSchema`, `QueryRequestSchema`等
- 响应模型：`CandidateDetailSchema`, `BatchReallocationResultSchema`等
- 内部模型：`EvaluationResultSchema`, `IntentionAnalysisSchema`等

### 3. llm_service.py - LLM集成
**职责**：调用Claude API完成智能任务

**核心方法**：
- `extract_candidate_info()`：从简历文本中提取结构化信息
- `analyze_job_intention()`：分析是否有明确求职意向
- `evaluate_candidate_for_position()`：为候选人对某岗位评分
- `analyze_position()`：分析岗位，提炼要求
- `match_position_to_intention()`：判断新岗位是否与意向匹配
- `understand_natural_language_query()`：理解自然语言查询
- `generate_query_summary()`：生成查询结果总结

### 4. pdf_processor.py - PDF处理
**职责**：从PDF中提取文本
- `extract_text_from_pdf()`：从文件提取
- `extract_text_from_bytes()`：从字节流提取

### 5. service.py - 核心业务逻辑
**职责**：实现所有业务流程

**核心方法**：
- `process_resume()`：处理上传的简历（7步流程）
- `create_position()`：创建新岗位（包括自动重新分配）
- `batch_reallocate_on_new_position()`：新增岗位时的重新分配逻辑

**处理三类候选人**：
1. 情况1：有意向 + 岗位存在 → 永不改动
2. 情况2：有意向 + 岗位不存在 → 等待匹配
3. 情况3：无意向 → 每新岗位评估一次

### 6. main.py - FastAPI应用
**职责**：提供所有REST API端点

**岗位管理API**：
- `POST /api/positions` - 创建新岗位
- `GET /api/positions` - 列表查询岗位
- `GET /api/positions/{id}` - 获取岗位详情
- `GET /api/positions/{id}/candidates` - 查看岗位的候选人

**候选人管理API**：
- `POST /api/candidates/upload` - 上传简历
- `GET /api/candidates/{id}` - 获取候选人详情
- `GET /api/candidates` - 列表查询候选人

**查询API**：
- `POST /api/query` - 自然语言查询
- `GET /api/health` - 健康检查

## 🔄 三大核心流程

### 流程1：简历处理（process_resume）

```
上传PDF
  ↓
[Step 1] 检查岗位库是否为空
  ├─ 为空 → 返回错误，提示先创建岗位
  └─ 非空 → 继续
  ↓
[Step 2] PDF文本提取（pdfplumber）
  ↓
[Step 3] 信息结构化提取（Claude LLM + JSON Schema）
  - 名字、年龄、邮箱、电话
  - 技能（技能名、等级、年限）
  - 工作经历（公司、职位、职责、成就）
  - 教育背景（学校、专业、学位）
  - 证书、自我评价、提取质量评分
  ↓
[Step 4] 求职意向分析（Claude LLM）
  - has_explicit_position: bool
  - explicit_position: str | null
  - explicit_position_source: str | null
  ↓
[Step 5] 对所有岗位评分（Claude LLM，并发）
  - 对每个岗位调用LLM评分
  - 输出：0-100分 + 等级(A/B/C/D) + 理由
  ↓
[Step 6] 分配最优岗位
  情况1：有意向 + 岗位存在
    → is_locked=TRUE, auto_matched=该岗位
  情况2：有意向 + 岗位不存在
    → is_locked=FALSE, no_matched=TRUE, auto_matched=当前最优
  情况3：无意向
    → is_locked=FALSE, no_matched=FALSE, auto_matched=当前最优
  ↓
[Step 7] 入库保存
  - 保存Candidate
  - 保存CandidateVersion
  - 保存所有CandidatePositionMatch
  - 记录AuditLog
```

### 流程2：岗位创建（create_position）

```
HR输入岗位信息
  ↓
[Step 1] LLM分析岗位
  - 提炼核心要求列表
  - 提炼加分项列表
  - 生成详细的评分指南
  ↓
[Step 2] 保存岗位
  - 插入Position表
  ↓
[Step 3] 触发自动重新分配
  调用 batch_reallocate_on_new_position()
  ↓
[Step 4] 返回变化报告
```

### 流程3：自动重新分配（batch_reallocate_on_new_position）

```
新增岗位事件
  ↓
扫描所有候选人
  ↓
for each candidate:
  
  分支A：有明确求职意向？
  │
  ├─ YES
  │  └─ 岗位是否被锁定？
  │     ├─ YES(已锁定) → SKIP（永不改）
  │     └─ NO(未锁定, no_matched=TRUE)
  │        └─ LLM判断新岗位是否与意向匹配
  │           ├─ YES → 更新+锁定+记录变化
  │           └─ NO  → SKIP（继续等待）
  │
  └─ NO（无明确意向）
     └─ 计算新岗位分数
        ├─ 新分数 > 当前最优分数？
        │  ├─ YES → 更新+记录变化
        │  └─ NO  → SKIP（保持不变）
        
↓
返回变化报告
```

## 🎯 关键设计决策

### 1. 60分基线
- **所有岗位统一60分基础要求**
- 不会因新岗位加入而改变
- 是绝对评分制，不是相对排名

### 2. 三层求职意向处理
- **情况1**：永不改动（尊重用户选择）
- **情况2**：等待修复（等待相应岗位创建）
- **情况3**：自适应（每新岗位重新评估）

### 3. 自动重新分配
- **新增岗位自动触发**（无需HR干预）
- **智能判断**（LLM判断意向匹配）
- **分数比较**（分数更高则更新）

### 4. 数据完整性
- **CandidatePositionMatch历史不改变**（审计追踪）
- **所有操作有日志**（完整审计）
- **版本控制**（候选人的多个版本）

## 📊 数据流向图

```
用户上传PDF
    ↓
llm_service.extract_candidate_info()
    ↓
service.process_resume()
    ├─ PDF解析
    ├─ 信息提取
    ├─ 意向分析
    ├─ 对所有岗位评分
    ├─ 分配最优岗位
    └─ 入库保存
    ↓
数据库写入
    ├─ Candidate
    ├─ CandidatePositionMatch（多条）
    ├─ CandidateVersion
    └─ AuditLog
    ↓
返回结果给用户
    ├─ candidate_id
    ├─ auto_matched_position
    ├─ auto_matched_score
    ├─ is_position_locked
    └─ no_matched_position


新增岗位
    ↓
llm_service.analyze_position()
    ↓
service.create_position()
    └─ service.batch_reallocate_on_new_position()
        ├─ 遍历所有候选人
        ├─ 三类分别处理
        ├─ LLM匹配意向
        ├─ LLM评分（可能）
        ├─ 更新Candidate
        ├─ 新增CandidatePositionMatch
        ├─ 记录PositionAllocationHistory
        └─ 记录AuditLog
    ↓
返回变化报告


用户查询
    ↓
llm_service.understand_natural_language_query()
    ↓
生成结构化查询参数
    ↓
main.natural_language_query()
    ├─ 执行相应的数据库查询
    ├─ 获取结果集
    └─ llm_service.generate_query_summary()
    ↓
返回结果 + 人类可读总结
```

## 🔧 快速部署指南

### 方式1：本地开发

```bash
# 1. 环境准备
cd recruitment_system
cp .env.example .env
# 编辑 .env，配置数据库和API密钥

# 2. 启动脚本
chmod +x start.sh
./start.sh

# 3. 访问
# 浏览器：http://localhost:8000/docs
```

### 方式2：Docker

```bash
# 1. 构建镜像
docker build -t recruitment-system .

# 2. 启动（需要PostgreSQL）
docker-compose up

# 3. 访问
# 浏览器：http://localhost:8000/docs
```

## ✅ 测试清单

在部署前请测试以下功能：

- [ ] 健康检查：`GET /api/health`
- [ ] 创建第一个岗位：`POST /api/positions`
- [ ] 上传简历：`POST /api/candidates/upload`
- [ ] 查看候选人：`GET /api/candidates/1`
- [ ] 查看岗位的候选人：`GET /api/positions/1/candidates`
- [ ] 自然语言查询：`POST /api/query`

## 🎓 学习路径

如果要理解系统设计，按以下顺序阅读：

1. **models.py** - 了解数据结构
2. **schemas.py** - 了解API数据格式
3. **service.py** - 了解核心业务逻辑
4. **llm_service.py** - 了解LLM集成
5. **main.py** - 了解API端点
6. **README.md** - 了解使用说明

## 🐛 常见问题

### Q1: 系统启动时报"岗位库为空"怎么办？
A: 这是正常的。系统需要先创建至少一个岗位才能处理简历。通过API创建岗位即可。

### Q2: 同一个候选人上传多份简历会怎样？
A: 系统会创建新的Candidate记录（不同的candidate_id），同时保存到CandidateVersion表保留历史。

### Q3: 如果新增岗位分数比较低怎么办？
A: 无明确意向的候选人会根据分数自动排序。有明确意向的候选人不会改动。

### Q4: 可以删除岗位吗？
A: 可以，但建议将is_active设置为FALSE进行软删除，而不是硬删除，以保留历史数据。

## 📈 后续优化方向

- [ ] 集成任务队列（Celery）处理异步任务
- [ ] 添加Redis缓存层提升查询性能
- [ ] 实现向量数据库支持（pgvector）
- [ ] 添加更多自然语言查询样本
- [ ] 集成背景调查API
- [ ] 多语言支持
- [ ] 前端界面（Streamlit或React）

## 📞 支持

如有问题，请查阅：
1. README.md - 完整的使用文档
2. FastAPI文档 - http://localhost:8000/docs
3. 日志输出 - 查看应用启动时的日志信息

---

**✅ 代码生成完成**  
**📅 生成时间**：2025年11月10日  
**📦 文件数**：11个Python模块 + 配置文件  
**🚀 状态**：可以立即部署和使用
