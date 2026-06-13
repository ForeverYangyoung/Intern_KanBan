"""
PyCharm 一键启动脚本
在 PyCharm 中右键此文件 -> Run 'run' 即可启动后端服务
"""
import sys
import os

# 强制 stdout/stderr 使用 UTF-8（Windows 默认 GBK 会导致中文/emoji 打印失败）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import uvicorn

if __name__ == "__main__":
    # 确保工作目录正确（兼容 PyCharm 运行时的工作目录问题）
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 将当前目录加入 Python 路径
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
