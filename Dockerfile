FROM python:3.11-slim

WORKDIR /app

# 复制后端代码
COPY backend/ /app/

# 复制前端构建产物（main.py 通过 Path(__file__).parent.parent / "frontend" / "dist" 访问）
COPY frontend/dist /frontend/dist

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
