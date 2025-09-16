#!/bin/bash
# 修复Celery Flower监控问题的脚本

set -e

echo "=========================================="
echo "修复Celery Flower监控问题"
echo "=========================================="
echo ""

# 检测操作系统
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
    PYTHON_EXE="api-gateway/.venv/Scripts/python.exe"
    PIP_EXE="api-gateway/.venv/Scripts/pip.exe"
else
    OS="unix"
    PYTHON_EXE="api-gateway/.venv/bin/python"
    PIP_EXE="api-gateway/.venv/bin/pip"
fi

echo "检测到操作系统: $OS"

# 检查虚拟环境
if [[ ! -f "$PYTHON_EXE" ]]; then
    echo "错误：虚拟环境不存在，请先运行 ./dev.sh start"
    exit 1
fi

echo ""
echo "步骤1: 安装Flower包..."
echo "----------------------------------------"
$PIP_EXE install flower==2.0.1

echo ""
echo "步骤2: 验证安装..."
echo "----------------------------------------"
if $PYTHON_EXE -c "import flower; print(f'Flower版本: {flower.__version__}')" 2>/dev/null; then
    echo "✓ Flower安装成功"
else
    echo "✗ Flower安装失败"
    exit 1
fi

echo ""
echo "步骤3: 测试Flower命令..."
echo "----------------------------------------"
cd data-processor
if ../$PYTHON_EXE -m celery -A tasks flower --help >/dev/null 2>&1; then
    echo "✓ Flower命令可用"
else
    echo "✗ Flower命令不可用"
    exit 1
fi
cd ..

echo ""
echo "=========================================="
echo "修复完成！"
echo "=========================================="
echo ""
echo "请执行以下操作："
echo "1. 停止当前服务: ./dev.sh stop"
echo "2. 重新启动服务: ./dev.sh start"
echo ""
echo "Celery监控地址: http://localhost:5555"
echo ""
