"""
上帝视角沙盒 — Demo 评委专用
支持一键模拟事件，触发双轨 Agent 响应
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.dependencies import SessionLocal
from app.models.database import (
    SandboxRun, Intern, MentorAlert, AlertLevel, AlertStatus,
    IngestEvent, IngestEventStatus, BreakdownEvent, RDSnapshot, SalesSnapshot
)
import random

router = APIRouter()


# ============================================================
# 请求模型
# ============================================================

class SimulateRequest(BaseModel):
    intern_id: int
    event: str


class RoleSwitchRequest(BaseModel):
    role: str   # intern / mentor / hr
    intern_id: int | None = None


# ============================================================
# 沙盒模拟事件
# ============================================================

@router.post("/simulate")
def simulate_event(req: SimulateRequest):
    """
    沙盒模拟事件注入
    支持事件类型：
      BUILD_FAIL_3X        — 研发：连续3次编译失败
      PRD_COMMENT_STUCK    — 产品：PRD评论僵局（语义争议未收敛）
      CRM_REJECT_3D        — 销售：CRM连续3天拒收
      CRM_SILENT_3D        — 销售：CRM静默3天（黄色提示）
    """
    db = SessionLocal()
    try:
        intern = db.query(Intern).filter(Intern.id == req.intern_id).first()
        if not intern:
            raise HTTPException(status_code=404, detail="实习生不存在")

        # 记录沙盒事件
        run = SandboxRun(
            operator="sandbox",
            simulated_intern_id=req.intern_id,
            event_type=req.event
        )
        db.add(run)

        result = {}

        if req.event == "BUILD_FAIL_3X":
            result = _simulate_build_fail_3x(db, intern)
        elif req.event == "PRD_COMMENT_STUCK":
            result = _simulate_prd_comment_stuck(db, intern)
        elif req.event == "CRM_REJECT_3D":
            result = _simulate_crm_reject_3d(db, intern)
        elif req.event == "CRM_SILENT_3D":
            result = _simulate_crm_silent_3d(db, intern)
        else:
            raise HTTPException(status_code=400, detail=f"未知事件类型: {req.event}")

        db.commit()
        return {
            "success": True,
            "event": req.event,
            "intern": intern.name,
            "job_family": intern.job_family,
            **result
        }
    finally:
        db.close()


def _simulate_build_fail_3x(db, intern):
    """研发：连续3次编译失败 → 触发白天轨 Copilot + 导师红点"""
    # 注入构建失败事件
    for i in range(3):
        evt = IngestEvent(
            intern_id=intern.id,
            source="SANDBOX",
            event_type="BUILD_FAIL",
            raw_payload={"build_id": f"sandbox-{i}", "error": "Redis connection pool port conflict"},
            status=IngestEventStatus.PROCESSED
        )
        db.add(evt)

    # 创建崩溃事件（白天轨）
    breakdown = BreakdownEvent(
        intern_id=intern.id,
        breakdown_type="BUILD_FAIL_3X",
        track="REALTIME",
        copilot_response={
            "root_cause": "Redis 连接池配置与本地端口冲突",
            "suggestion": "检查 redis.conf 中 maxIdle 配置，参考团队 Wiki P127",
            "copilot_text": "⚠️ 检测到连续 3 次编译失败\n根因提示：Redis 连接池配置与本地端口冲突\n[查看团队排障小抄] [问我具体问题]"
        }
    )
    db.add(breakdown)

    # 创建导师预警（红色）
    alert = MentorAlert(
        mentor_id=intern.mentor_id,
        intern_id=intern.id,
        alert_level=AlertLevel.RED,
        cheat_sheet_text=f"【沙盒模拟】{intern.name} 连续3次编译失败，疑似 Redis 配置问题。建议：1) 推送排障小抄；2) 安排 1v1 排查。",
        status=AlertStatus.ACTIVE
    )
    db.add(alert)
    db.flush()

    return {
        "track": "REALTIME",
        "copilot_triggered": True,
        "alert_id": alert.id,
        "alert_level": "RED",
        "copilot_message": "⚠️ 检测到连续 3 次编译失败\n根因提示：Redis 连接池配置与本地端口冲突",
        "mentor_notified": True,
    }


def _simulate_prd_comment_stuck(db, intern):
    """产品：PRD评论僵局（语义争议未收敛48h）→ Product Agent 共识备忘录"""
    # 注入 PRD 评论事件
    evt = IngestEvent(
        intern_id=intern.id,
        source="SANDBOX",
        event_type="PRD_COMMENT_STUCK",
        raw_payload={
            "prd_id": "PRD-SANDBOX-001",
            "comments": [
                "技术可行性有问题，建议降低范围",
                "业务边界不清晰，需要产品明确",
                "技术方案评审时再讨论",
                "这个需求优先级应该降低",
                "我不同意当前的方案",
            ],
            "stuck_hours": 72
        },
        status=IngestEventStatus.PROCESSED
    )
    db.add(evt)

    # 创建崩溃事件（白天轨）
    breakdown = BreakdownEvent(
        intern_id=intern.id,
        breakdown_type="PRD_COMMENT_STUCK",
        track="REALTIME",
        copilot_response={
            "consensus_memo": "检测到 PRD 评论区存在「技术可行性争议」与「业务边界争议」两类语义聚类，已持续 72h 未收敛。建议导师介入引导技术方案评审。",
            "clusters": ["TECH_FEASIBILITY_DISPUTE", "BUSINESS_BOUNDARY_DISPUTE"]
        }
    )
    db.add(breakdown)

    # 创建导师预警（黄色，非直接标风险）
    alert = MentorAlert(
        mentor_id=intern.mentor_id,
        intern_id=intern.id,
        alert_level=AlertLevel.YELLOW,
        cheat_sheet_text=f"【沙盒模拟】{intern.name} 的 PRD 评论区出现语义争议（技术可行性 + 业务边界），已 72h 未收敛。建议：引导技术方案评审，避免误伤啃硬骨头的 PM。",
        status=AlertStatus.ACTIVE
    )
    db.add(alert)
    db.flush()

    return {
        "track": "REALTIME",
        "copilot_triggered": True,
        "alert_id": alert.id,
        "alert_level": "YELLOW",
        "consensus_memo": "检测到两类语义聚类：技术可行性争议 / 业务边界争议",
        "mentor_notified": True,
    }


def _simulate_crm_reject_3d(db, intern):
    """销售：CRM连续3天拒收 → 销售 Copilot + 黄色提示"""
    # 注入 CRM 拒收事件
    today = datetime.now().date()
    for i in range(3):
        snap = SalesSnapshot(
            intern_id=intern.id,
            crm_leads_touched=0,
            effective_call_duration=0,
            snapshot_date=today,
        )
        db.add(snap)

    # 创建崩溃事件
    breakdown = BreakdownEvent(
        intern_id=intern.id,
        breakdown_type="CRM_REJECT_3D",
        track="REALTIME",
        copilot_response={
            "copilot_text": f"⚠️ {intern.name} CRM 连续 3 天零触达，疑似话术卡点。建议：安排绩优同事 shadow 半天。"
        }
    )
    db.add(breakdown)

    # 创建导师预警（黄色，非红色——废除一刀切）
    alert = MentorAlert(
        mentor_id=intern.mentor_id,
        intern_id=intern.id,
        alert_level=AlertLevel.YELLOW,
        cheat_sheet_text=f"【沙盒模拟】{intern.name} CRM 连续 3 天零触达，非直接判失联。建议：1) 安排绩优同事 shadow；2) 检查话术通关情况。",
        status=AlertStatus.ACTIVE
    )
    db.add(alert)
    db.flush()

    return {
        "track": "REALTIME",
        "copilot_triggered": True,
        "alert_id": alert.id,
        "alert_level": "YELLOW",
        "copilot_message": f"⚠️ {intern.name} CRM 连续 3 天零触达，疑似话术卡点",
        "mentor_notified": True,
    }


def _simulate_crm_silent_3d(db, intern):
    """销售：CRM静默3天 → 仅黄色提示，不标风险（v3.0 修正）"""
    # 注入 CRM 静默事件（有触达但无有效通话）
    today = datetime.now().date()
    snap = SalesSnapshot(
        intern_id=intern.id,
        crm_leads_touched=5,
        effective_call_duration=0,  # 有触达但无有效通话
        snapshot_date=today,
    )
    db.add(snap)

    # 创建崩溃事件
    breakdown = BreakdownEvent(
        intern_id=intern.id,
        breakdown_type="CRM_SILENT_3D",
        track="REALTIME",
        copilot_response={
            "copilot_text": f"💛 {intern.name} CRM 有触达但连续 3 天无有效通话，可能是话术卡点（非失联）。建议：安排话术复盘。"
        }
    )
    db.add(breakdown)

    # 创建导师预警（黄色，仅提示）
    alert = MentorAlert(
        mentor_id=intern.mentor_id,
        intern_id=intern.id,
        alert_level=AlertLevel.YELLOW,
        cheat_sheet_text=f"【沙盒模拟】{intern.name} 有 CRM 触达但连续 3 天无有效通话，可能是话术卡点（非失联）。建议安排话术复盘，勿直接判红灯。",
        status=AlertStatus.ACTIVE
    )
    db.add(alert)
    db.flush()

    return {
        "track": "REALTIME",
        "copilot_triggered": True,
        "alert_id": alert.id,
        "alert_level": "YELLOW",
        "copilot_message": f"💛 {intern.name} 有触达但无有效通话，疑似话术卡点（非失联）",
        "mentor_notified": True,
    }


# ============================================================
# 沙盒：查询模拟历史
# ============================================================

@router.get("/runs")
def get_sandbox_runs():
    """查询沙盒模拟历史"""
    db = SessionLocal()
    try:
        runs = db.query(SandboxRun).order_by(SandboxRun.id.desc()).limit(50).all()
        return [
            {
                "id": r.id,
                "operator": r.operator,
                "intern_id": r.simulated_intern_id,
                "event_type": r.event_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
    finally:
        db.close()


@router.get("/interns")
def get_sandbox_interns():
    """获取所有实习生（供沙盒下拉选择）"""
    db = SessionLocal()
    try:
        interns = db.query(Intern).all()
        return [
            {
                "id": i.id,
                "name": i.name,
                "job_family": i.job_family,
                "current_state": i.current_state,
                "recruiter_tag": i.recruiter_tag,
                "mentor_id": i.mentor_id,
            }
            for i in interns
        ]
    finally:
        db.close()
