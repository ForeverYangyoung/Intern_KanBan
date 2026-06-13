"""
数据模型定义 — 严格遵循 DEV_DOC v1.0 生产级数据库表结构
重构为基于里程碑事件与双向质检的全新 schema
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, JSON,
    ForeignKey, Enum, Boolean, Date
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# ============================================================
# 枚举类型
# ============================================================

class JobFamily(str, enum.Enum):
    """岗位隔离"""
    RD = "RD"        # 研发线
    PM = "PM"        # 产品线
    SALES = "SALES"  # 销售线


class StateNode(str, enum.Enum):
    """状态机三大阶段"""
    ONBOARDING = "ONBOARDING"    # 融入期
    RAMP_UP = "RAMP_UP"          # 上手期
    INDEPENDENT = "INDEPENDENT"  # 独立期


class RecruiterTag(str, enum.Enum):
    """招聘风控联动打标"""
    LIGHTNING = "LIGHTNING"  # 绩优闪电
    STEADY = "STEADY"        # 正常稳健
    RISK = "RISK"            # 红灯风险


class AlertLevel(str, enum.Enum):
    """预警级别"""
    YELLOW = "YELLOW"
    RED = "RED"


class AlertStatus(str, enum.Enum):
    """预警状态"""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


# ============================================================
# 1. 实习生基础表（状态机核心）
# ============================================================

class Intern(Base):
    """实习生 — 状态机核心"""
    __tablename__ = "interns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    job_family = Column(Enum(JobFamily), nullable=False, comment="岗位隔离: RD/PM/SALES")
    mentor_id = Column(Integer, nullable=False)
    current_state = Column(
        Enum(StateNode), default=StateNode.ONBOARDING,
        comment="状态机当前阶段"
    )
    recruiter_tag = Column(
        Enum(RecruiterTag), default=RecruiterTag.STEADY,
        comment="招聘风控联动打标"
    )
    entry_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ============================================================
# 2. 岗位标准里程碑配置表（确定性 SOP 状态机底座）
# ============================================================

class MilestoneConfig(Base):
    """岗位标准里程碑配置 — 确定性 SOP 底座"""
    __tablename__ = "milestone_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_family = Column(Enum(JobFamily), nullable=False)
    state_node = Column(Enum(StateNode), nullable=False)
    milestone_name = Column(String(100), nullable=False)
    trigger_event = Column(
        String(50), nullable=False,
        comment="触发事件: FIRST_PR_MERGED / CRM_FIRST_CALL 等"
    )
    required_count = Column(Integer, default=1)


# ============================================================
# 3. 研发绩效结构化快照表（对接腾讯工蜂/TAPD）
# ============================================================

class RDSnapshot(Base):
    """研发绩效快照 — 对接工蜂/TAPD"""
    __tablename__ = "rd_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    commit_count = Column(Integer, default=0)
    pr_merged_count = Column(Integer, default=0)
    bug_resolved_count = Column(Integer, default=0)
    cr_total_comments = Column(Integer, default=0)
    raw_cr_log = Column(JSON, default=None, comment="非结构化 CR 原始文本，供 LLM 审计")
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 4. 销售绩效结构化快照表（对接企微 CRM）
# ============================================================

class SalesSnapshot(Base):
    """销售绩效快照 — 对接企微 CRM"""
    __tablename__ = "sales_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    crm_leads_touched = Column(Integer, default=0, comment="触达线索数")
    effective_call_duration = Column(Integer, default=0, comment="有效通话时长（秒）")
    raw_followup_summaries = Column(
        JSON, default=None,
        comment="企微跟进小结非结构化文本，供 LLM 审计"
    )
    snapshot_date = Column(Date, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 5. 双向一致性校验日志表（防反向 AI 作弊侦探）
# ============================================================

class ConsistencyCheck(Base):
    """双向一致性校验 — 防作弊侦探"""
    __tablename__ = "consistency_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    check_date = Column(Date, nullable=False)
    reported_text_summary = Column(Text, comment="腾讯文档中手写的日报/周报提炼")
    actual_log_summary = Column(Text, comment="工蜂/TAPD/CRM 行为提取")
    is_conflict = Column(Boolean, default=False, comment="是否触发虚高欺骗预警")
    ai_detect_insight = Column(Text, comment="AI 侦探给出的矛盾证据摘要")
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 6. 异常合并与 AI 带教小抄表
# ============================================================

class MentorAlert(Base):
    """异常合并与 AI 带教小抄"""
    __tablename__ = "mentor_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mentor_id = Column(Integer, nullable=False)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    alert_level = Column(Enum(AlertLevel), nullable=False)
    cheat_sheet_text = Column(Text, nullable=False, comment="压缩后的 100 字带教小抄")
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE)
    version = Column(Integer, default=1, comment="乐观锁版本号")
    created_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, default=None)


# ============================================================
# 7. 导师表（保留原设计的扩展）
# ============================================================

class Mentor(Base):
    """导师"""
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    department = Column(String(100))
    wecom_userid = Column(String(100), comment="企业微信 UserID，用于消息推送")
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 8. 成长地图 & 任务（保留原 MVP 功能，与状态机解耦）
# ============================================================

class GrowthMap(Base):
    """成长地图 — 阶段计划"""
    __tablename__ = "growth_maps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    phase_name = Column(String(50), nullable=False)
    phase_order = Column(Integer, nullable=False)
    date_start = Column(DateTime, nullable=False)
    date_end = Column(DateTime, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, server_default=func.now())


class GrowthTask(Base):
    """成长地图 — 具体任务"""
    __tablename__ = "growth_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    map_id = Column(Integer, ForeignKey("growth_maps.id"), nullable=False)
    dimension = Column(String(50), nullable=False, comment="能力维度: 技术/业务/协作/产出")
    title = Column(String(200), nullable=False)
    description = Column(Text)
    source = Column(String(20), default="system", comment="来源: system/mentor/self")
    status = Column(String(20), default="pending")
    estimated_hours = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CustomTask(Base):
    """实习生自定义事项"""
    __tablename__ = "custom_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    title = Column(String(200), nullable=False)
    time_range = Column(String(50), comment="时间段")
    status = Column(String(20), default="pending")
    created_date = Column(DateTime, server_default=func.now())


# ============================================================
# 9. 数据采集事件表（Webhook / 沙盒注入）
# ============================================================

class IngestEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class IngestEvent(Base):
    """数据采集事件 — Webhook / 沙盒注入"""
    __tablename__ = "ingest_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    source = Column(String(50), nullable=False, comment="GONGFENG/TAPD/WECOM_CRM/SANDBOX")
    event_type = Column(String(50), nullable=False)
    raw_payload = Column(JSON, default=None)
    status = Column(Enum(IngestEventStatus), default=IngestEventStatus.PENDING)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 10. 崩溃事件表（双轨标记）
# ============================================================

class BreakdownEvent(Base):
    """崩溃卡点事件 — 双轨标记"""
    __tablename__ = "breakdown_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    breakdown_type = Column(String(50), nullable=False)
    track = Column(String(20), default="REALTIME", comment="REALTIME/NIGHTLY")
    copilot_response = Column(JSON, default=None)
    triggered_at = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, default=None)


# ============================================================
# 11. 举证式带教 + 绩效素材表
# ============================================================

class MentorContributionLog(Base):
    """举证式带教 + 绩效素材"""
    __tablename__ = "mentor_contribution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mentor_id = Column(Integer, nullable=False)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    alert_id = Column(Integer, default=None)
    raw_input = Column(Text, nullable=False, comment="导师原始语音转写/文字")
    performance_summary = Column(Text, default=None, comment="混元生成的组织建设贡献描述")
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 12. 智能成长错题本
# ============================================================

class GrowthErrorBook(Base):
    """智能成长错题本"""
    __tablename__ = "growth_error_book"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    error_pattern = Column(String(100), nullable=False, comment="如 REDIS_BOUNDARY_DEADLOCK")
    occurrence_count = Column(Integer, default=1)
    last_seen_at = Column(DateTime, server_default=func.now())
    ai_summary = Column(Text, default=None)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 13. 看板缓存表
# ============================================================

class DashboardCache(Base):
    """看板缓存"""
    __tablename__ = "dashboard_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(20), nullable=False, comment="MENTOR/HR")
    owner_id = Column(Integer, nullable=False)
    cache_payload = Column(JSON, default=None)
    generated_at = Column(DateTime, server_default=func.now())


# ============================================================
# 14. 沙盒模拟事件记录表（Demo 专用）
# ============================================================

class SandboxRun(Base):
    """沙盒模拟事件记录 — Demo 专用"""
    __tablename__ = "sandbox_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator = Column(String(50), nullable=False)
    simulated_intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# 辅助：建表后的种子数据插入
# ============================================================

SEED_MILESTONES = [
    # 研发线 (RD)
    {"job_family": JobFamily.RD, "state_node": StateNode.ONBOARDING, "milestone_name": "开发环境配置完成",       "trigger_event": "DEV_ENV_SETUP_DONE",      "required_count": 1},
    {"job_family": JobFamily.RD, "state_node": StateNode.ONBOARDING, "milestone_name": "通过基础代码规范考核",     "trigger_event": "CODE_STANDARD_PASSED",    "required_count": 1},
    {"job_family": JobFamily.RD, "state_node": StateNode.RAMP_UP,     "milestone_name": "独立修复首个线上Bug",      "trigger_event": "FIRST_BUG_RESOLVED",       "required_count": 1},
    {"job_family": JobFamily.RD, "state_node": StateNode.RAMP_UP,     "milestone_name": "合入首个小需求PR",         "trigger_event": "FIRST_PR_MERGED",          "required_count": 1},
    {"job_family": JobFamily.RD, "state_node": StateNode.INDEPENDENT, "milestone_name": "独立Owner核心业务模块",      "trigger_event": "MODULE_OWNERSHIP_ASSIGNED","required_count": 1},
    {"job_family": JobFamily.RD, "state_node": StateNode.INDEPENDENT, "milestone_name": "TAPD需求交付准时率达标",   "trigger_event": "DELIVERY_ON_TIME_3_WEEKS", "required_count": 3},
    # 产品线 (PM)
    {"job_family": JobFamily.PM, "state_node": StateNode.ONBOARDING, "milestone_name": "阅读产品引导文档",          "trigger_event": "GUIDE_DOC_READ",            "required_count": 1},
    {"job_family": JobFamily.PM, "state_node": StateNode.ONBOARDING, "milestone_name": "完成竞品分析思维导图",      "trigger_event": "COMPETITOR_ANALYSIS_DONE", "required_count": 1},
    {"job_family": JobFamily.PM, "state_node": StateNode.RAMP_UP,     "milestone_name": "输出首份完整PRD并通过评审",   "trigger_event": "FIRST_PRD_APPROVED",        "required_count": 1},
    {"job_family": JobFamily.PM, "state_node": StateNode.INDEPENDENT, "milestone_name": "主导核心版本迭代需求池规划", "trigger_event": "REQUIREMENT_POOL_OWNERSHIP","required_count": 1},
    # 销售线 (SALES)
    {"job_family": JobFamily.SALES, "state_node": StateNode.ONBOARDING, "milestone_name": "销售话术通关",             "trigger_event": "SALES_SCRIPT_PASSED",      "required_count": 1},
    {"job_family": JobFamily.SALES, "state_node": StateNode.ONBOARDING, "milestone_name": "熟悉CRM系统操作",           "trigger_event": "CRM_SYSTEM_FAMILIAR",     "required_count": 1},
    {"job_family": JobFamily.SALES, "state_node": StateNode.RAMP_UP,     "milestone_name": "独立外呼并沉淀有效意向客户", "trigger_event": "CRM_FIRST_CALL",          "required_count": 1},
    {"job_family": JobFamily.SALES, "state_node": StateNode.INDEPENDENT, "milestone_name": "独立完成全链路商务谈判",     "trigger_event": "FULL_DEAL_CLOSED",         "required_count": 1},
]


def seed_milestone_configs(session):
    """插入岗位标准里程碑种子数据"""
    from sqlalchemy import select
    existing = session.execute(select(MilestoneConfig.id).limit(1)).first()
    if existing:
        return
    for item in SEED_MILESTONES:
        session.add(MilestoneConfig(**item))
    session.commit()
    print(f"[Seed] 已插入 {len(SEED_MILESTONES)} 条里程碑配置")


# ============================================================
# 完整 Demo 模拟数据 — 体现实习生成长变化轨迹
# ============================================================

from datetime import date, timedelta, datetime as dt

DEMO_DATA = {
    "mentors": [
        Mentor(id=1, name="王建国", department="技术研发部", wecom_userid="wangjianguo"),
        Mentor(id=2, name="李思琪", department="产品设计部", wecom_userid="liqiqi"),
        Mentor(id=3, name="张伟明", department="销售运营部", wecom_userid="zhangweiming"),
    ],
    "interns": [
        # 研发实习生 — 绩优闪电（已进入独立期）
        Intern(id=1, name="张三", job_family=JobFamily.RD, mentor_id=1,
               current_state=StateNode.INDEPENDENT, recruiter_tag=RecruiterTag.LIGHTNING,
               entry_date=date(2026, 4, 15)),
        # 研发实习生 — 正常稳健（上手期）
        Intern(id=2, name="李四", job_family=JobFamily.RD, mentor_id=1,
               current_state=StateNode.RAMP_UP, recruiter_tag=RecruiterTag.STEADY,
               entry_date=date(2026, 5, 10)),
        # 产品实习生 — 正常稳健（融入期）
        Intern(id=3, name="王五", job_family=JobFamily.PM, mentor_id=2,
               current_state=StateNode.ONBOARDING, recruiter_tag=RecruiterTag.STEADY,
               entry_date=date(2026, 5, 25)),
        # 销售实习生 — 红灯风险（融入期停滞）
        Intern(id=4, name="赵六", job_family=JobFamily.SALES, mentor_id=3,
               current_state=StateNode.RAMP_UP, recruiter_tag=RecruiterTag.RISK,
               entry_date=date(2026, 5, 8)),
        # 研发实习生 — 正常（上手期，刚转过来）
        Intern(id=5, name="孙七", job_family=JobFamily.RD, mentor_id=1,
               current_state=StateNode.RAMP_UP, recruiter_tag=RecruiterTag.STEADY,
               entry_date=date(2026, 5, 28)),
    ],
    "growth_maps": {
        # 张三的成长地图（已到第3阶段-独立期）
        1: [
            GrowthMap(id=1, intern_id=1, phase_name="融入期 - 环境熟悉与规范学习", phase_order=1,
                      date_start=dt(2026, 4, 15, 9, 0), date_end=dt(2026, 5, 13, 18, 0), status="completed"),
            GrowthMap(id=2, intern_id=1, phase_name="上手期 - 小需求实践与技能提升", phase_order=2,
                      date_start=dt(2026, 5, 14, 9, 0), date_end=dt(2026, 7, 12, 18, 0), status="completed"),
            GrowthMap(id=3, intern_id=1, phase_name="独立期 - 核心模块Owner与交付保障", phase_order=3,
                      date_start=dt(2026, 7, 13, 9, 0), date_end=dt(2026, 9, 30, 18, 0), status="in_progress"),
        ],
        # 李四的成长地图（在第2阶段-上手期）
        2: [
            GrowthMap(id=4, intern_id=2, phase_name="融入期 - 环境熟悉与规范学习", phase_order=1,
                      date_start=dt(2026, 5, 10, 9, 0), date_end=dt(2026, 6, 7, 18, 0), status="completed"),
            GrowthMap(id=5, intern_id=2, phase_name="上手期 - 小需求实践与技能提升", phase_order=2,
                      date_start=dt(2026, 6, 8, 9, 0), date_end=dt(2026, 8, 6, 18, 0), status="in_progress"),
            GrowthMap(id=6, intern_id=2, phase_name="独立期 - 核心模块Owner与交付保障", phase_order=3,
                      date_start=dt(2026, 8, 7, 9, 0), date_end=dt(2026, 10, 31, 18, 0), status="pending"),
        ],
        # 王五的成长地图（在第1阶段-融入期）
        3: [
            GrowthMap(id=7, intern_id=3, phase_name="融入期 - 环境熟悉与规范学习", phase_order=1,
                      date_start=dt(2026, 5, 25, 9, 0), date_end=dt(2026, 6, 22, 18, 0), status="in_progress"),
            GrowthMap(id=8, intern_id=3, phase_name="上手期 - 需求分析与产品思维培养", phase_order=2,
                      date_start=dt(2026, 6, 23, 9, 0), date_end=dt(2026, 8, 21, 18, 0), status="pending"),
            GrowthMap(id=9, intern_id=3, phase_name="独立期 - 版本规划与需求池管理", phase_order=3,
                      date_start=dt(2026, 8, 22, 9, 0), date_end=dt(2026, 11, 15, 18, 0), status="pending"),
        ],
        # 赵六的成长地图（融入期，有风险）
        4: [
            GrowthMap(id=10, intern_id=4, phase_name="融入期 - 话术培训与CRM熟悉", phase_order=1,
                       date_start=dt(2026, 5, 8, 9, 0), date_end=dt(2026, 6, 5, 18, 0), status="in_progress"),
            GrowthMap(id=11, intern_id=4, phase_name="上手期 - 独立外呼与客户沉淀", phase_order=2,
                       date_start=dt(2026, 6, 6, 9, 0), date_end=dt(2026, 8, 4, 18, 0), status="pending"),
            GrowthMap(id=12, intern_id=4, phase_name="独立期 - 全链路商务谈判", phase_order=3,
                       date_start=dt(2026, 8, 5, 9, 0), date_end=dt(2026, 10, 28, 18, 0), status="pending"),
        ],
        # 孙七的成长地图
        5: [
            GrowthMap(id=13, intern_id=5, phase_name="融入期 - 环境熟悉与规范学习", phase_order=1,
                      date_start=dt(2026, 5, 28, 9, 0), date_end=dt(2026, 6, 25, 18, 0), status="completed"),
            GrowthMap(id=14, intern_id=5, phase_name="上手期 - 小需求实践与技能提升", phase_order=2,
                      date_start=dt(2026, 6, 26, 9, 0), date_end=dt(2026, 8, 24, 18, 0), status="in_progress"),
            GrowthMap(id=15, intern_id=5, phase_name="独立期 - 核心模块Owner与交付保障", phase_order=3,
                      date_start=dt(2026, 8, 25, 9, 0), date_end=dt(2026, 11, 17, 18, 0), status="pending"),
        ],
    },
    "tasks": {
        # 张三当前阶段任务
        3: [  # map_id=3 是张三的独立期
            GrowthTask(id=1, map_id=3, dimension="技术", title="独立负责用户中心模块重构", description="负责用户登录/注册/权限管理模块的架构升级", source="system", status="done", estimated_hours=40),
            GrowthTask(id=2, map_id=3, dimension="产出", title="TAPD需求 INT-2026-089 准时交付", description="用户画像标签功能开发", source="system", status="done", estimated_hours=24),
            GrowthTask(id=3, map_id=3, dimension="技术", title="Code Review 新人代码审核（每周≥3次）", description="参与组内CR流程，帮助新人成长", source="mentor", status="in_progress", estimated_hours=8),
            GrowthTask(id=4, map_id=3, dimension="协作", title="主导技术方案评审会", description="输出技术方案并组织评审", source="system", status="pending", estimated_hours=16),
        ],
        # 李四当前阶段任务
        5: [
            GrowthTask(id=5, map_id=5, dimension="技术", title="完成Git工作流培训并提交首个Commit", description="学习分支策略和提交规范", source="system", status="done", estimated_hours=4),
            GrowthTask(id=6, map_id=5, dimension="技术", title="阅读并理解项目核心代码架构", description="重点看路由层和数据层设计", source="system", status="in_progress", estimated_hours=16),
            GrowthTask(id=7, map_id=5, dimension="业务", title="参与Bug Bash活动，修复至少1个线上Bug", description="通过实际修bug熟悉业务逻辑", source="mentor", status="pending", estimated_hours=8),
            GrowthTask(id=8, map_id=5, dimension="产出", title="合入首个Feature PR", description="在导师指导下完成小功能开发", source="system", status="pending", estimated_hours=24),
        ],
        # 王五当前阶段任务
        7: [
            GrowthTask(id=9, map_id=7, dimension="业务", title="阅读产品引导文档（共5篇）", description="了解公司产品矩阵、目标用户、商业模式", source="system", status="done", estimated_hours=8),
            GrowthTask(id=10, map_id=7, dimension="业务", title="完成竞品分析思维导图", description="选择2-3款竞品做深度分析", source="system", status="in_progress", estimated_hours=12),
            GrowthTask(id=11, map_id=7, dimension="协作", title="参加3次产品评审会议旁听", description="每次输出200字参会笔记", source="mentor", status="pending", estimated_hours=6),
            GrowthTask(id=12, map_id=7, dimension="产出", title="输出1份功能点分析报告", description="针对现有产品的某个功能做深度拆解", source="system", status="pending", estimated_hours=10),
        ],
        # 赵六当前阶段任务（多项未完成→触发风险）
        10: [
            GrowthTask(id=13, map_id=10, dimension="业务", title="销售话术通关考核", description="背诵并演练标准话术", source="system", status="overdue", estimated_hours=8),
            GrowthTask(id=14, map_id=10, dimension="业务", title="熟悉CRM系统操作", description="掌握线索录入、跟进、转化全流程", source="system", status="in_progress", estimated_hours=6),
            GrowthTask(id=15, map_id=10, dimension="协作", title="跟随导师进行3次客户电话跟听", description="记录通话要点和导师技巧", source="mentor", status="pending", estimated_hours=4),
        ],
        # 孙七当前阶段任务
        14: [
            GrowthTask(id=16, map_id=14, dimension="技术", title="开发环境配置（IDE+Git+数据库）", description="搭建本地开发环境", source="system", status="done", estimated_hours=4),
            GrowthTask(id=17, map_id=14, dimension="技术", title="通过基础代码规范考核", description="编码规范考试80分以上", source="system", status="done", estimated_hours=6),
            GrowthTask(id=18, map_id=14, dimension="业务", title="阅读团队Wiki知识库", description="重点了解业务背景和技术选型", source="system", status="in_progress", estimated_hours=12),
            GrowthTask(id=19, map_id=14, dimension="协作", title="参加每日站会并做自我介绍", description="融入团队氛围", source="mentor", status="pending", estimated_hours=2),
        ],
    },
    # 研发绩效周度快照（体现张三的成长轨迹）
    "rd_snapshots": {
        1: [  # 张三
            RDSnapshot(intern_id=1, commit_count=0, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=0, snapshot_date=date(2026, 4, 19)),
            RDSnapshot(intern_id=1, commit_count=5, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=3, snapshot_date=date(2026, 4, 26)),
            RDSnapshot(intern_id=1, commit_count=12, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=8, snapshot_date=date(2026, 5, 3)),
            RDSnapshot(intern_id=1, commit_count=21, pr_merged_count=0, bug_resolved_count=1, cr_total_comments=14, snapshot_date=date(2026, 5, 10)),
            RDSnapshot(intern_id=1, commit_count=35, pr_merged_count=1, bug_resolved_count=2, cr_total_comments=22, snapshot_date=date(2026, 5, 17)),   # 首个PR合入 → 触发 RAMP_UP
            RDSnapshot(intern_id=1, commit_count=52, pr_merged_count=1, bug_resolved_count=3, cr_total_comments=31, snapshot_date=date(2026, 5, 24)),
            RDSnapshot(intern_id=1, commit_count=71, pr_merged_count=2, bug_resolved_count=5, cr_total_comments=42, snapshot_date=date(2026, 5, 31)),
            RDSnapshot(intern_id=1, commit_count=93, pr_merged_count=3, bug_resolved_count=7, cr_total_comments=56, snapshot_date=date(2026, 6, 7)),
            RDSnapshot(intern_id=1, commit_count=118, pr_merged_count=4, bug_resolved_count=9, cr_total_comments=72, snapshot_date=date(2026, 6, 14)),
        ],
        2: [  # 李四
            RDSnapshot(intern_id=2, commit_count=0, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=0, snapshot_date=date(2026, 5, 17)),
            RDSnapshot(intern_id=2, commit_count=3, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=2, snapshot_date=date(2026, 5, 24)),
            RDSnapshot(intern_id=2, commit_count=8, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=5, snapshot_date=date(2026, 5, 31)),
            RDSnapshot(intern_id=2, commit_count=15, pr_merged_count=0, bug_resolved_count=1, cr_total_comments=9, snapshot_date=date(2026, 6, 7)),
            RDSnapshot(intern_id=2, commit_count=24, pr_merged_count=1, bug_resolved_count=1, cr_total_comments=15, snapshot_date=date(2026, 6, 14)),
        ],
        5: [  # 孙七
            RDSnapshot(intern_id=5, commit_count=0, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=0, snapshot_date=date(2026, 6, 4)),
            RDSnapshot(intern_id=5, commit_count=4, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=1, snapshot_date=date(2026, 6, 11)),
            RDSnapshot(intern_id=5, commit_count=9, pr_merged_count=0, bug_resolved_count=0, cr_total_comments=4, snapshot_date=date(2026, 6, 14)),
        ],
    },
    # 销售绩效周度快照（赵六的——数据低迷触发风险）
    "sales_snapshots": {
        4: [
            SalesSnapshot(intern_id=4, crm_leads_touched=0, effective_call_duration=0, snapshot_date=date(2026, 5, 15)),
            SalesSnapshot(intern_id=4, crm_leads_touched=2, effective_call_duration=120, snapshot_date=date(2026, 5, 22)),
            SalesSnapshot(intern_id=4, crm_leads_touched=3, effective_call_duration=180, snapshot_date=date(2026, 5, 29)),   # 远低于同岗均值
            SalesSnapshot(intern_id=4, crm_leads_touched=1, effective_call_duration=60, snapshot_date=date(2026, 6, 5)),     # 回落！风险信号
            SalesSnapshot(intern_id=4, crm_leads_touched=2, effective_call_duration=90, snapshot_date=date(2026, 6, 12)),   # 持续低迷
        ],
    },
    # 导师预警
    "alerts": [
        MentorAlert(id=1, mentor_id=3, intern_id=4, alert_level=AlertLevel.RED,
                    cheat_sheet_text="赵六连续3周触达线索数低于同岗均值50%，话术通关超期未过。建议：(1)安排1v1面谈了解困难；(2)降低本周KPI至3条有效触达；(3)配对绩优同事 shadow 两天。",
                    status=AlertStatus.ACTIVE),
        MentorAlert(id=2, mentor_id=1, intern_id=2, alert_level=AlertLevel.YELLOW,
                    cheat_sheet_text="李四上手期进展正常但偏慢，PR合入数略低于同期平均水平。建议：可适当分配更小粒度的task帮助积累confidence。",
                    status=AlertStatus.ACTIVE),
        MentorAlert(id=3, mentor_id=1, intern_id=1, alert_level=AlertLevel.YELLOW,
                    cheat_sheet_text="张三进入独立期后表现优异，建议开始承担code review职责，同时可考虑提前转正评估。",
                    status=AlertStatus.RESOLVED, resolved_at=dt(2026, 6, 10, 10, 0)),
    ],
    # 自定义事项
    "custom_tasks": {
        1: [CustomTask(id=1, intern_id=1, title="深入学习 Rust 异步编程模型", time_range="周末 2h/周", status="done"),
            CustomTask(id=2, intern_id=1, title="参加内部技术分享会《微服务治理实战》", time_range="周四晚", status="in_progress")],
        2: [CustomTask(id=3, intern_id=2, title="复习计算机网络基础知识", time_range="每晚1h", status="in_progress")],
        3: [CustomTask(id=4, intern_id=3, title="学习 Figma 高级交互技巧", time_range="周末", status="pending")],
        4: [],
        5: [CustomTask(id=5, intern_id=5, title="刷 LeetCode 每日一题", time_range="每天30min", status="in_progress")],
    },
}


def seed_demo_data(session):
    """插入完整的 Demo 模拟数据 — 体现实习生成长轨迹"""
    from sqlalchemy import select

    # 检查是否已有数据
    existing_intern = session.execute(select(Intern.id).limit(1)).first()
    if existing_intern:
        return  # 已有数据，跳过

    # 1. 插入导师
    for m in DEMO_DATA["mentors"]:
        session.add(m)
    session.flush()
    print(f"[Seed] 已插入 {len(DEMO_DATA['mentors'])} 名导师")

    # 2. 插入实习生
    for intern_obj in DEMO_DATA["interns"]:
        session.add(intern_obj)
    session.flush()
    print(f"[Seed] 已插入 {len(DEMO_DATA['interns'])} 名实习生")

    # 3. 插入成长地图
    for maps_list in DEMO_DATA["growth_maps"].values():
        for gm in maps_list:
            session.add(gm)
    session.flush()
    total_maps = sum(len(v) for v in DEMO_DATA["growth_maps"].values())
    print(f"[Seed] 已插入 {total_maps} 个成长阶段")

    # 4. 插入任务
    total_tasks = 0
    for tasks_list in DEMO_DATA["tasks"].values():
        for task in tasks_list:
            session.add(task)
            total_tasks += 1
    session.flush()
    print(f"[Seed] 已插入 {total_tasks} 个任务")

    # 5. 插入研发快照
    for snapshots_list in DEMO_DATA["rd_snapshots"].values():
        for snap in snapshots_list:
            session.add(snap)
    session.flush()
    total_rd = sum(len(v) for v in DEMO_DATA["rd_snapshots"].values())
    print(f"[Seed] 已插入 {total_rd} 条研发绩效快照")

    # 6. 插入销售快照
    for snapshots_list in DEMO_DATA["sales_snapshots"].values():
        for snap in snapshots_list:
            session.add(snap)
    session.flush()
    print(f"[Seed] 已插入 {sum(len(v) for v in DEMO_DATA['sales_snapshots'].values())} 条销售绩效快照")

    # 7. 插入预警
    for alert in DEMO_DATA["alerts"]:
        session.add(alert)
    session.flush()
    print(f"[Seed] 已插入 {len(DEMO_DATA['alerts'])} 条导师预警")

    # 8. 插入自定义事项
    for tasks_list in DEMO_DATA["custom_tasks"].values():
        for ct in tasks_list:
            session.add(ct)
    session.flush()
    total_ct = sum(len(v) for v in DEMO_DATA["custom_tasks"].values())
    print(f"[Seed] 已插入 {total_ct} 条自定义事项")

    session.commit()
    print("[Seed] [OK] Demo data initialized!")
