#!/bin/bash
# 启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}智能招聘助手系统 - 启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查环境变量
if [ ! -f .env ]; then
    echo -e "${RED}✗ .env 文件不存在${NC}"
    echo -e "${YELLOW}请复制 .env 文件并配置数据库和API密钥${NC}"
    exit 1
fi

echo -e "${GREEN}✓ .env 文件已找到${NC}"

# 检查Python版本
python_version=$(python3 --version 2>&1)
echo -e "${GREEN}✓ Python 版本: $python_version${NC}"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv venv
fi

echo -e "${GREEN}✓ 激活虚拟环境${NC}"
source venv/bin/activate

# 安装依赖
echo -e "${YELLOW}安装/更新依赖...${NC}"
pip install -r requirements.txt -q

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 依赖安装完成${NC}"
else
    echo -e "${RED}✗ 依赖安装失败${NC}"
    exit 1
fi

# 加载环境变量
export $(cat .env | grep -v '^#' | xargs)

# 检查数据库连接
echo -e "${YELLOW}检查数据库连接...${NC}"
python3 -c "
from models import init_db
import os
try:
    init_db(os.getenv('DATABASE_URL'))
    print('✓ 数据库连接成功')
except Exception as e:
    print(f'✗ 数据库连接失败: {str(e)}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ 数据库初始化失败${NC}"
    exit 1
fi

# 启动应用
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}启动应用服务器...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}API文档: http://localhost:8000/docs${NC}"
echo -e "${GREEN}健康检查: http://localhost:8000/api/health${NC}"
echo ""

python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
