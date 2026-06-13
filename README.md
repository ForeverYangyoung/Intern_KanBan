# 实习能量站 - 新人成长导航智能看板

## 项目结构

```
intern-growth-platform/
├── frontend/                # Vue3 + TDesign 前端
│   ├── src/
│   │   ├── views/           # 页面组件
│   │   │   ├── InternDashboard.vue   # 实习生每日看板
│   │   │   ├── GrowthMap.vue         # 成长地图
│   │   │   ├── MentorDashboard.vue   # 导师预警工作台
│   │   │   └── HRDashboard.vue       # HR周报
│   │   ├── components/      # 通用组件
│   │   ├── stores/          # Pinia 状态管理
│   │   ├── router/          # 路由配置
│   │   ├── api/             # 接口封装
│   │   └── utils/           # 工具函数
│   └── package.json
│
├── backend/                 # Python FastAPI 后端
│   ├── app/
│   │   ├── routers/         # API 路由
│   │   │   ├── intern.py    # 实习生端接口
│   │   │   ├── mentor.py    # 导师端接口
│   │   │   ├── hr.py        # HR端接口
│   │   │   └── ai.py        # AI服务接口
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 业务服务
│   │   │   ├── ai_service.py        # AI 核心服务
│   │   │   └── data_collector.py    # 多源数据采集
│   │   └── schemas/         # Pydantic 模型
│   ├── main.py              # FastAPI 入口
│   └── requirements.txt
```

## 快速启动

### 1. 前端启动

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

### 2. 后端启动

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# API 文档 http://localhost:8000/docs
```

## 核心设计理念

1. **无感采集**: 对接 Git/Tapd/企微/文档平台，自动感知行为
2. **只报异常**: 正常的不展示，只推送需要关注的人/事
3. **一键决策**: 导师只需"看一眼→点一下"，不在系统里多停留
4. **成长可见**: 成长地图 = 阶段 × 能力维度表格，全程可追踪

## 部署指南

### 前端部署（EdgeOne Pages / 腾讯云 COS）

```bash
cd frontend
npm run build
# 将 dist/ 目录部署到静态托管服务
```

### 后端部署（腾讯云轻量服务器）

```bash
# 使用 supervisor 或 systemd 管理进程
# 或使用 Docker:
docker build -t intern-growth-api .
docker run -d -p 8000:8000 intern-growth-api
```

### 环境变量配置

编辑 `backend/.env`:
```
AI_API_KEY=你的大模型API密钥
DATABASE_URL=mysql+pymysql://user:pass@host:3306/intern_growth
WECOM_WEBHOOK_URL=企微机器人Webhook地址
```
