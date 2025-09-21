#!/usr/bin/env python3
"""
Elasticsearch服务检查脚本

检查Elasticsearch是否正在运行，如果没有运行则尝试启动
"""

import sys
import os
import subprocess
import time
import requests
from datetime import datetime

def log_info(message):
    """打印信息日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] {message}")

def log_error(message):
    """打印错误日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {message}")

def log_success(message):
    """打印成功日志"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SUCCESS] {message}")

def check_elasticsearch_running():
    """检查Elasticsearch是否正在运行"""
    try:
        response = requests.get("http://localhost:9200", timeout=5)
        if response.status_code == 200:
            data = response.json()
            log_success(f"Elasticsearch正在运行: {data.get('version', {}).get('number', 'unknown')}")
            return True
    except Exception as e:
        log_info(f"Elasticsearch未运行: {e}")
    return False

def start_elasticsearch():
    """启动Elasticsearch服务"""
    log_info("尝试启动Elasticsearch...")
    
    # 项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    elasticsearch_dir = os.path.join(project_root, 'vendor', 'elasticsearch')
    
    # 查找Elasticsearch安装目录
    if os.path.exists(elasticsearch_dir):
        # 查找当前版本目录
        current_path_file = os.path.join(elasticsearch_dir, 'current.path')
        if os.path.exists(current_path_file):
            with open(current_path_file, 'r') as f:
                es_base_dir = f.read().strip()
            
            if os.path.exists(es_base_dir):
                es_bat = os.path.join(es_base_dir, 'bin', 'elasticsearch.bat')
                if os.path.exists(es_bat):
                    log_info(f"找到Elasticsearch: {es_bat}")
                    
                    # 启动Elasticsearch
                    try:
                        # 使用PowerShell启动
                        ps_cmd = f"""
                        Start-Process -FilePath '{es_bat}' -ArgumentList '-Epath.data=./data-dev','-Ehttp.port=9200','-Enetwork.host=127.0.0.1','-Expack.security.enabled=false','-Ediscovery.type=single-node' -WindowStyle Hidden
                        """
                        subprocess.run(['powershell', '-NoProfile', '-Command', ps_cmd], 
                                     check=True, capture_output=True)
                        
                        log_info("Elasticsearch启动命令已发送，等待服务就绪...")
                        
                        # 等待服务启动
                        for i in range(30):
                            time.sleep(2)
                            if check_elasticsearch_running():
                                log_success("Elasticsearch已成功启动")
                                return True
                            log_info(f"等待Elasticsearch启动... ({i+1}/30)")
                        
                        log_error("Elasticsearch启动超时")
                        return False
                        
                    except Exception as e:
                        log_error(f"启动Elasticsearch失败: {e}")
                        return False
                else:
                    log_error(f"未找到Elasticsearch可执行文件: {es_bat}")
            else:
                log_error(f"Elasticsearch目录不存在: {es_base_dir}")
        else:
            log_error("未找到Elasticsearch版本信息文件")
    else:
        log_error(f"Elasticsearch安装目录不存在: {elasticsearch_dir}")
    
    return False

def main():
    """主函数"""
    print("=" * 50)
    print("Elasticsearch服务检查脚本")
    print("=" * 50)
    
    if check_elasticsearch_running():
        log_success("Elasticsearch服务正常")
        return 0
    
    log_info("Elasticsearch未运行，尝试启动...")
    if start_elasticsearch():
        log_success("Elasticsearch启动成功")
        return 0
    else:
        log_error("Elasticsearch启动失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())
