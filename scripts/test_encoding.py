#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试UTF-8编码支持
"""

import sys
import os

# Windows环境设置UTF-8编码
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # 重新配置标准输出流
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

print("Python版本:", sys.version)
print("平台:", sys.platform)
print("默认编码:", sys.getdefaultencoding())
print("stdout编码:", sys.stdout.encoding)
print("stderr编码:", sys.stderr.encoding)
print()
print("测试Emoji和中文输出:")
print("✓ 检查通过")
print("🚀 启动成功")
print("🔧 配置完成")
print("📊 数据已加载")
print("中文测试：你好世界！")
print()
print("如果以上内容都正常显示，说明编码问题已解决！")
