# 实习能量站 · 新人成长导航智能看板

## 开发文档 v3.0（Demo 落地闭环版）

> 最后更新：2026-06-13

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心目标与设计原则](#2-核心目标与设计原则)
3. [系统架构](#3-系统架构)
4. [技术选型](#4-技术选型)
5. [功能模块说明](#5-功能模块说明)
6. [数据模型](#6-数据模型)
7. [API 接口文档](#7-api-接口文档)
8. [AI 能力说明](#8-ai-能力说明)
9. [数据采集与清洗边界（合规铁律）](#9-数据采集与清洗边界合规铁律)
10. [导师触达策略](#10-导师触达策略)
11. [部署方案](#11-部署方案)
12. [迭代路线](#12-迭代路线)
13. [致命缺陷清单（v2.0 复盘）](#13-致命缺陷清单v20-复盘)
14. [Demo 上帝视角沙盒](#14-demo-上帝视角沙盒)

---

## 1. 项目概述

### 1.1 项目背景与痛点对齐

业务部新人（20 名校招实习生，分布在研发、产品、销售岗位）培养过程中存在以下跨角色协同痛点：

| 角色 | 痛点描述 | 核心根因 |
|------|---------|---------|
| **实习生** | 不知道学什么，产生转正焦虑；频繁私聊 HR 问进度 | 岗位成长路径不透明，缺乏确定性的里程碑反馈 |
| **业务导师** | 带教凭经验，节奏难把控；日常业务极忙，无暇登录独立看板 | 缺乏标准岗位 SOP 状态机，系统触达流噪声过载 |
| **HR** | 被动承接实习生与导师的沟通损耗，无法掌握全局动态 | 各方数据孤岛，缺乏结构化的过程性评价动态表 |
| **招聘同学** | 常来追问"这批人适岗情况如何"，无法及时做留用风控决策 | 缺乏在途的过程行为衍生数据支撑，无法提前锁定优质人才或启动补招 |

### 1.2 解决方案：独立 Web Demo + 双轨流式 Agent

「实习能量站」是一套 **TDesign 独立 Web + FastAPI + MySQL + Redis** 的里程碑状态机智能看板 Demo，通过 **白天实时 Copilot + 深夜深度批处理** 双轨架构实现：

- **实习生：** 独立 Web 通关看板（`/intern`）；崩溃卡点 **秒级弹窗 Copilot**（「检测到配置死锁，要看团队排障小抄吗？」），非马后炮。
- **业务导师：** 企微侧边栏常驻看板 + 独立 Web；消红点须 **举证式带教记录**（语音/文字），混元自动沉淀为年终绩效素材。
- **HR 与招聘：** Web 全景看板；深夜批处理产出常模排名与【绩优闪电/红灯风险】打标。
- **评委 Demo：** 顶部 **上帝视角沙盒**，3 分钟切换角色、一键模拟「连续编译失败」「PRD 评论僵局」等事件，实时看系统响应。

### 1.3 核心价值

不搞隐私监控；AI 不当电子警察；**白天撞墙即导航、深夜算排名**；废除腾讯多维表宿主，独立 Web 实现行级权限隔离；导师带教成果 **绩效利益捆绑**，拒绝自欺欺人的红点消灭术。

---

## 2. 核心目标与设计原则

### 2.1 北极星指标

**"缩短实习生从入职到独立产出的时间"**

### 2.2 硬约束

> 导师带教操作 ≤ 1 分钟（但消红点须提交 **一句带教核心**，非空点）

### 2.3 核心设计原则

| 原则 | 管理与工程含义 |
|------|---------------|
| **独立 Web 脱钩多维表** | **废除腾讯文档多维表作为前端宿主**。TDesign + FastAPI 自建 Demo，严格行级数据隔离，绕过第三方 API 限流（429）与权限泄漏风险。 |
| **双轨流式 Agent** | **白天轨**：Webhook 命中硬崩溃信号 → 实时调 Hunyuan-Standard → 实习生弹窗 Copilot。<br>**深夜轨**：02:00–05:00 批处理脏数据清洗、常模排名、风控打标、看板缓存。 |
| **真机能 Agent（非规则计数）** | 废除「PRD 评论 ≥50 = 风险」等一刀切硬编码；研发/产品 Agent 用 Tool Calling 与语义聚类做真诊断。 |
| **举证式红点消除** | 导师点击「已线下点拨」须强制输入 **一句带教核心**（语音或文字）；混元转写为「组织建设贡献描述」写入导师绩效素材库。 |
| **合规无感采集** | 严禁抓取群聊私聊；仅采集工蜂/TAPD/企微 CRM 等交付影子日志。 |

### 2.4 崩溃卡点定义（硬信号触发白天实时轨）

| 岗位 | 硬崩溃信号（规则引擎命中 → **立即** 调混元-Standard，非等凌晨） |
|------|----------------------------------------------------------------|
| **研发** | 连续 3 次编译/构建失败；同一 PR CR 驳回 ≥ 3 次 |
| **产品** | PRD 评论区 **语义聚类** 识别「技术可行性争议」或「业务边界争议」且 **48h 未收敛**（非单纯评论数 ≥50） |
| **销售** | CRM 连续 3 天拒收 **且** 同期无有效通话记录；CRM 静默超阈值 → 黄色提示（非直接判失联杀单） |

---

## 3. 系统架构

### 3.1 双轨流式 Agent 数据流

```
                    ┌─────────────────────────────────────┐
                    │  日常数据流入（Webhook / 沙盒模拟）    │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────┐
                    │  蓄水池（RabbitMQ / TDMQ）入队即 200   │
                    └──────────────────┬──────────────────┘
                                       │
              ┌────────────────────────┴────────────────────────┐
              │                                                 │
              ▼ 白天轨（实时）                                    ▼ 深夜轨（批处理）
    硬崩溃信号命中                                      02:00–05:00 Worker
    FastAPI 同步调混元-Standard                         脏数据清洗 + 常模 Norming
    → 实习生 Web 弹窗 Copilot                           + 风控打标 + 智能成长错题本
    → 导师看板实时红点 + Copilot 小抄                   → dashboard_cache（Redis）
              │                                                 │
              └────────────────────────┬────────────────────────┘
                                       ▼
                    ┌─────────────────────────────────────┐
                    │  独立 Web（TDesign）+ 企微常驻看板      │
                    │  实习生 / 导师 / HR 三端秒开读缓存     │
                    └─────────────────────────────────────┘
```

### 3.2 分层架构

```
「实习能量站」Demo 落地闭环架构（v3.0）

┌─────────────────────────────────────────────────────────────────────────┐
│ 【前端层 · 独立 Web（TDesign Vue Next）】                                 │
│  /intern  实习生通关看板 + 实时 Copilot 弹窗                              │
│  /mentor  导师看板（可嵌入企微侧边栏）+ 举证式消红点                      │
│  /hr      HR/招聘风控全景                                                 │
│  /sandbox 上帝视角沙盒（评委 Demo 专用，置顶）                            │
├─────────────────────────────────────────────────────────────────────────┤
│ 【蓄水池层 RabbitMQ / TDMQ】                                              │
├─────────────────────────────────────────────────────────────────────────┤
│ 【业务逻辑层 FastAPI + MySQL + Redis】                                    │
│  状态机引擎 │ 双轨调度器（realtime_agent / nightly_batch）                │
├─────────────────────────────────────────────────────────────────────────┤
│ 【AI Agent 层 腾讯混元】                                                  │
│  白天：Hunyuan-Standard 流式 Copilot 弹窗                                 │
│  深夜：Hunyuan-Pro 深度分析 + 成长错题本 + 绩效素材生成                    │
│  Dev Agent（Tool Calling）│ Product Agent（语义聚类）│ Growth Error Book │
├─────────────────────────────────────────────────────────────────────────┤
│ 【数据采集层 Webhook + 沙盒事件注入】                                     │
│  工蜂 / TAPD / 企微 CRM │ SandboxController 模拟事件                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 技术选型

| 层级 | 技术选型 | 选型理由 |
|------|---------|---------|
| **前端** | TDesign Vue Next + Vite | 腾讯开源设计体系；**独立 Web Demo**，行级 RBAC，无多维表 API 限流。 |
| **后端** | Python FastAPI | 异步 Webhook 入队 + 白天轨同步 Copilot 低延迟响应。 |
| **数据库** | MySQL | 实习生/状态机/错题本/绩效素材持久化。 |
| **缓存** | Redis | 看板快照、实时红点、流式 Agent 会话上下文。 |
| **消息队列** | RabbitMQ / 腾讯云 TDMQ | 蓄水池削峰；白天轨与深夜轨解耦。 |
| **AI 大模型** | 腾讯混元 | **Standard**（白天实时 Copilot）+ **Pro**（深夜深度 Agent + 错题本）。 |
| **部署** | CloudBase 云托管 / 轻量服务器 | Demo 一键 Docker 部署。 |

> **已废除**：腾讯文档多维表作为实习生前端宿主。

---

## 5. 功能模块说明

### 5.1 里程碑状态机（核心资产）

Webhook 入队后 **轻量 Consumer 实时更新里程碑计数**；AI 诊断走双轨 Agent，不在状态机路径阻塞。

#### 5.1.1 状态机拓扑

```
[ONBOARDING] --(基础通关)--> [RAMP_UP] --(核心交付)--> [INDEPENDENT]
```

#### 5.1.2 三大岗位差异化判定矩阵

| 阶段 | 研发线 | 产品线 (PM) | 销售线 |
|------|--------|------------|--------|
| **ONBOARDING** | 工蜂 首次 Commit | 思维导图完整度（规则） | ASR 话术通关 |
| **RAMP_UP** | 首个 Bug 修复 + PR 合入<br>**Agent：** Dev Agent Tool Calling 抓日志/Diff | 首份 PRD 过审<br>**Agent：** Product Agent 语义聚类争议类型 | 首批意向客户<br>**Agent：** 拒收模式 Copilot |
| **INDEPENDENT** | 模块 Owner + 准时率 | 需求池主导 + 关联树 | 全链路谈判 + 回款 |

### 5.2 实习生端：独立 Web 通关看板（`/intern`）

**页面宿主**：TDesign 独立 Web（**废除腾讯多维表**）。

| 模块 | 说明 |
|------|------|
| **今日待办** | 按状态机节点从 SOP 库动态拉取 |
| **实时 Copilot 弹窗** | 白天轨命中硬崩溃信号后 **秒级弹窗**：「检测到配置死锁，要看团队排障小抄吗？」流式输出建议 |
| **主动提问** | 随时向 Copilot 提问（不参与风控打分） |
| **成长错题本** | 深夜轨汇总个人卡点模式，实习期末转正评审佐证 |

#### 5.2.1 白天轨实时 Copilot 交互示例

```
┌─ 实习能量站 ─────────────────────────────────────┐
│  ⚠️ 检测到连续 3 次编译失败                        │
│  根因提示：Redis 连接池配置与本地端口冲突           │
│  [ 查看团队排障小抄 ]  [ 问我具体问题 ]  [ 稍后处理 ] │
│  （混元-Standard 流式输出中...）                   │
└──────────────────────────────────────────────────┘
```

### 5.3 导师端：常驻看板 + 举证式消红点（`/mentor`）

可嵌入企微侧边栏，亦可独立 Web 访问。

#### 5.3.1 举证式红点消除（对抗导师懒惰）

导师点击 **[已线下点拨]** 时，系统 **强制** 要求：

- 输入 **一句带教核心**（文字），或录制 **≤30 秒语音**
- 不可空点消红点

**绩效利益捆绑**：混元-Pro 将口语化带教内容转写为标准化 **「组织建设贡献描述」**，写入 `mentor_contribution_logs`，可直接用于导师年终绩效/晋升材料（带教从负担变为 **刷绩效积分**）。

#### 5.3.2 看板交互架构

```
┌─ 带教看板 ─────────────────────────────────────────┐
│  🔴 小王 · 研发 · Redis PR 3 次 CR 驳回              │
│  💡 Dev Agent 小抄：边界死锁修复 Diff 建议            │
│  [ 推送资料 ]  [ 拉协助群 ]                          │
│  [ 已线下点拨 ] → 强制弹窗：                          │
│      「请用一句话/语音输入本次点拨核心」              │
│      🎤 [语音] 或 📝 [文字]  → 混元生成绩效素材      │
├────────────────────────────────────────────────────┤
│  🟢 小张 / 小李（折叠）                               │
└────────────────────────────────────────────────────┘
```

### 5.4 HR 与招聘端（`/hr`）

- **常模规范化**：深夜轨批处理产出岗位池百分位排名
- **风控打标**：【绩优闪电】【正常稳健】【红灯风险】—— 由深夜轨计算，非白天实时轨
- **成长错题本汇总**：转正评审时展示实习生卡点演化轨迹

### 5.5 AI Agent 机能（真机能，非规则计数）

#### 5.5.1 Dev Agent（研发）

- **Tool Calling**：自动拉取工蜂 **错误日志 + Git Diff**
- 输出 **代码级修改建议**（非单纯统计行数/驳回次数）
- 触发：编译失败 streak / CR 驳回 streak（白天轨实时）

#### 5.5.2 Product Agent（产品）

- **废除**「评论数 ≥50 = 风险」一刀切规则
- LLM **语义聚类** 评论区：识别「技术可行性争议」vs「业务边界争议」
- 输出 **《共识备忘录》** 给导师，帮收敛而非误伤啃硬骨头的优秀 PM

#### 5.5.3 智能成长错题本（Growth Error Book）

- 深夜轨后台归纳实习生 **重复卡点模式**（如「Redis 边界条件」连续出现）
- 沉淀为结构化错题本，供 HR 转正评审与导师复盘引用

---

## 6. 数据模型

### 6.1 核心表结构（MySQL）

```sql
-- 实习生（行级 RBAC：intern 仅看自己，mentor 看名下，hr 看全部）
CREATE TABLE `interns` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `job_family` enum('RD', 'PM', 'SALES') NOT NULL,
  `mentor_id` bigint NOT NULL,
  `current_state` enum('ONBOARDING', 'RAMP_UP', 'INDEPENDENT') DEFAULT 'ONBOARDING',
  `recruiter_tag` enum('LIGHTNING', 'STEADY', 'RISK') DEFAULT 'STEADY',
  `entry_date` date NOT NULL,
  `updated_at` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE `ingest_events` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `intern_id` bigint NOT NULL,
  `source` enum('GONGFENG', 'TAPD', 'WECOM_CRM', 'SANDBOX') NOT NULL,
  `event_type` varchar(50) NOT NULL,
  `raw_payload` json NOT NULL,
  `status` enum('PENDING', 'PROCESSED', 'FAILED') DEFAULT 'PENDING',
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE `breakdown_events` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `intern_id` bigint NOT NULL,
  `breakdown_type` varchar(50) NOT NULL,
  `track` enum('REALTIME', 'NIGHTLY') NOT NULL, -- 双轨标记
  `copilot_response` json,
  `triggered_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `resolved_at` timestamp NULL
);

CREATE TABLE `mentor_alerts` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `mentor_id` bigint NOT NULL,
  `intern_id` bigint NOT NULL,
  `alert_level` enum('YELLOW', 'RED') NOT NULL,
  `cheat_sheet_text` text NOT NULL,
  `status` enum('ACTIVE', 'PENDING_EVIDENCE', 'RESOLVED') DEFAULT 'ACTIVE',
  `version` int DEFAULT 1,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP
);

-- 举证式带教 + 绩效素材
CREATE TABLE `mentor_contribution_logs` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `mentor_id` bigint NOT NULL,
  `intern_id` bigint NOT NULL,
  `alert_id` bigint NOT NULL,
  `raw_input` text NOT NULL,        -- 导师原始语音转写/文字
  `performance_summary` text NOT NULL, -- 混元生成的组织建设贡献描述
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP
);

-- 智能成长错题本
CREATE TABLE `growth_error_book` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `intern_id` bigint NOT NULL,
  `error_pattern` varchar(100) NOT NULL, -- 如 REDIS_BOUNDARY_DEADLOCK
  `occurrence_count` int DEFAULT 1,
  `last_seen_at` timestamp DEFAULT CURRENT_TIMESTAMP,
  `ai_summary` text
);

CREATE TABLE `dashboard_cache` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `role` enum('MENTOR', 'HR') NOT NULL,
  `owner_id` bigint NOT NULL,
  `cache_payload` json NOT NULL,
  `generated_at` timestamp DEFAULT CURRENT_TIMESTAMP
);

-- 沙盒模拟事件记录（Demo 专用）
CREATE TABLE `sandbox_runs` (
  `id` bigint PRIMARY KEY AUTO_INCREMENT,
  `operator` varchar(50) NOT NULL,
  `simulated_intern_id` bigint NOT NULL,
  `event_type` varchar(50) NOT NULL,
  `created_at` timestamp DEFAULT CURRENT_TIMESTAMP
);
```

### 6.2 双轨数据处理流

```
Webhook / 沙盒注入
    → MQ 入队（200）
    → 轻量 Consumer：更新快照 + 里程碑计数
    → 硬崩溃信号？
         ├─ YES → 白天轨：realtime_agent.py
         │         混元-Standard 流式 Copilot
         │         WebSocket 推实习生弹窗 + 导师看板红点
         └─ NO  → 仅持久化，等深夜轨

02:00–05:00 nightly_batch.py
    → 脏数据清洗
    → 常模 Norming + 风控打标
    → Product Agent 语义聚类（PRD 争议）
    → 成长错题本归纳
    → dashboard_cache 写入 Redis
```

---

## 7. API 接口文档

### 7.1 Webhook（入队即成功）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/webhook/gongfeng/build` | 构建失败事件 → 可能触发白天轨 |
| POST | `/api/webhook/gongfeng/pr` | PR/CR 变动 |
| POST | `/api/webhook/tapd/story` | TAPD 状态变更 |
| POST | `/api/webhook/wecom/crm` | CRM 跟进 |

### 7.2 实习生实时 Copilot（WebSocket 流式）

`WS /api/v1/intern/copilot/stream` — 白天轨弹窗流式输出

`POST /api/v1/intern/copilot/ask` — 主动提问

### 7.3 导师举证消红点

`POST /api/v1/mentor/resolve-with-evidence`

```json
{
  "alert_id": 88,
  "mentor_id": 9527,
  "evidence_type": "TEXT",
  "evidence_content": "指出了 Redis 连接池 maxIdle 配置问题，并带着看了团队标准示例",
  "expected_version": 3
}
```

响应含 `performance_summary`（已写入绩效素材库）。

### 7.4 上帝视角沙盒（Demo）

`POST /api/v1/sandbox/simulate`

```json
{
  "intern_id": 1024,
  "event": "BUILD_FAIL_3X"
}
```

可选 `event`：`BUILD_FAIL_3X` | `PRD_COMMENT_STUCK` | `CRM_REJECT_3D` | `ROLE_SWITCH_DEV_XIAOWANG`

---

## 8. AI 能力说明

入口：`backend/app/services/ai_service.py` + `backend/app/agents/`

### 8.1 双轨调度

| 轨道 | 时机 | 模型 | 职责 |
|------|------|------|------|
| **白天轨** | 硬崩溃信号命中后 **秒级** | Hunyuan-Standard | 流式 Copilot 弹窗、Dev/Product 即时导航 |
| **深夜轨** | 02:00–05:00 | Hunyuan-Pro | Norming、风控打标、错题本、绩效素材、共识备忘录 |

### 8.2 Agent 实现要点

```python
# Dev Agent — Tool Calling
async def dev_agent_diagnose(intern_id: int) -> dict:
    """
    Tools: fetch_build_log(), fetch_git_diff(), fetch_cr_comments()
    输出: code_level_fix_suggestions（非行数统计）
    """

# Product Agent — 语义聚类（废除评论数≥50规则）
async def product_agent_consensus_memo(prd_comments: list) -> dict:
    """
    聚类: TECH_FEASIBILITY_DISPUTE | BUSINESS_BOUNDARY_DISPUTE
    输出: consensus_memo_for_mentor
    触发: 争议类型已识别 + 48h 未收敛（非单纯评论计数）
    """

# 导师绩效素材生成
async def generate_mentor_contribution(raw_voice_or_text: str) -> str:
    """
    输入: 导师一句带教核心
    输出: 组织建设贡献描述（写入 mentor_contribution_logs）
    """

# 成长错题本（深夜轨）
async def update_growth_error_book(intern_id: int) -> list:
    """
    归纳重复卡点模式，供转正评审引用
    """
```

---

## 9. 数据采集与清洗边界（合规铁律）

### 9.1 隐私红线

严禁采集群聊/私聊文字；仅采集工蜂/TAPD/企微 CRM 交付影子日志。

### 9.2 脏数据清洗（深夜轨执行）

- 代码防刷（500 行开源拷贝剔除）
- 协作刷分清洗（CR 互评降权 50%）
- 挂机噪音剔除

---

## 10. 导师触达策略

| 策略 | 说明 |
|------|------|
| **实时红点** | 白天轨命中崩溃信号 → 导师看板 **即时** 红点（非等凌晨） |
| **常驻看板** | 企微侧边栏 / 独立 Web，读 Redis 缓存秒开 |
| **举证消红点** | 不可空点；语音/文字 → 绩效素材 |
| **无 9:00 轰炸** | 废除每日卡片推送；仅 RED 级可选弱提醒 |
| **深夜更新排名** | Norming/打标由深夜轨写入，早晨 HR 看最新 |

---

## 11. 部署方案

```bash
# 前端
cd frontend && npm install && npm run dev    # :3000

# 后端
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# MQ + Redis
docker run -d -p 5672:5672 rabbitmq:3-management
docker run -d -p 6379:6379 redis:7

# 深夜 Worker（本地手动）
python -m app.workers.nightly_batch

# 生产
docker build -t intern-growth-api . && docker run -p 8000:8000 --env-file .env intern-growth-api
```

---

## 12. 迭代路线（Demo 落地闭环）

| 版本 | 周期 | 交付物 | Demo 考点 |
|------|------|--------|----------|
| **V1.0** | 第 1 周 | 独立 Web（TDesign）三端 + MQ 蓄水池 + 状态机 + **上帝视角沙盒** | 3 分钟切换角色模拟事件 |
| **V1.5** | 第 2 周 | **白天轨** 实时 Copilot 弹窗（WebSocket 流式） | 撞墙秒级响应，非马后炮 |
| **V2.0** | 第 3 周 | Dev/Product Agent + **举证消红点** + 绩效素材 | 真机能 Agent + 反导师懒惰 |
| **V2.5** | 第 4 周 | 深夜轨 Norming/打标 + **成长错题本** + HR 全景 | 双轨闭环完整 |

---

## 13. 致命缺陷清单（v2.0 复盘）

| 缺陷 | v2.0 问题 | v3.0 修正 |
|------|----------|----------|
| **时效性破产（马后炮导航）** | 崩溃卡点仅凌晨 02:00–05:00 扫描；下午 2 点崩溃深夜才通知 | **白天轨**：硬信号命中 → 秒级混元 Copilot 弹窗 |
| **多维表前端灾难** | 腾讯多维表 API 429 限流；行级权限无法隔离，销售线索易泄漏 | **独立 Web + MySQL RBAC**；废除多维表宿主 |
| **一刀切规则（逆向淘汰优秀人才）** | PRD 评论 ≥50 自动标风险；CRM 静默 3 天 = 失联杀单 | Product Agent **语义聚类**；销售静默仅黄色提示 + 举证核实 |
| **管理流产（自欺红点消灭术）** | 一键消红点，导师 KPI 压力下空点，小抄进垃圾桶 | **举证式消红点** + 混元生成 **绩效贡献素材** |

---

## 14. Demo 上帝视角沙盒

**路径**：独立 Web 顶部置顶 `[沙盒模拟面板]`（仅 Demo 环境开启）

**功能**：评委 3 分钟演示闭环，无需真实工蜂/TAPD 回调。

| 操作 | 说明 |
|------|------|
| **切换视角** | 下拉选择「研发小王」「产品小张」「销售小李」及对应导师/HR |
| **一键模拟事件** | `连续 3 次编译失败` → 实习生弹窗 Copilot + 导师红点 |
| | `PRD 评论僵局（语义争议未收敛）` → Product Agent 共识备忘录 |
| | `CRM 连续 3 天拒收` → 销售 Copilot + 黄色提示 |
| **实时观测** | 沙盒面板展示 Webhook 入队 → 白天轨/深夜轨分流日志 |

```json
POST /api/v1/sandbox/simulate
{ "intern_id": 1024, "event": "BUILD_FAIL_3X" }
```

---

## 附录

### A. 文件结构

```
intern-growth-platform/
├── frontend/src/
│   ├── views/
│   │   ├── InternDashboard.vue    # /intern + Copilot 弹窗
│   │   ├── MentorDashboard.vue    # /mentor + 举证消红点
│   │   ├── HRDashboard.vue
│   │   └── SandboxPanel.vue       # 上帝视角沙盒
│   └── api/
├── backend/app/
│   ├── routers/ webhook.py, intern.py, mentor.py, sandbox.py
│   ├── agents/ dev_agent.py, product_agent.py
│   ├── workers/ nightly_batch.py, realtime_agent.py
│   └── services/ ai_service.py, state_machine.py
```

### B. TDesign 组件

Card, Table, Badge, Dialog（举证弹窗）, Input, Upload（语音）, Alert（Copilot 流式）, Select（沙盒角色切换）, Button
