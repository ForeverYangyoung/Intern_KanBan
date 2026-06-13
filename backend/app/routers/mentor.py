"""
导师端 API 路由 — 冷热隔离看板 + 新工作流

新工作流（祛除反人性设计）：
1. [已阅知晓] → 一键关闭红点，不阻塞
2. [记录带教要点] → 自愿操作，可得绩效积分
3. 绩效素材预览 → 展示"带教能给你带来什么利益"
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sa_func
from datetime import datetime

from app.dependencies import get_db, ConcurrencySafeSession
from app.models.database import (
    Intern, Mentor, GrowthMap, GrowthTask,
    MentorAlert, AlertLevel, AlertStatus, StateNode, RecruiterTag, JobFamily,
    RDSnapshot, SalesSnapshot, MentorContributionLog
)

router = APIRouter()


class ActionRequest(BaseModel):
    action: str  # PUSH_DOC | CREATE_GROUP | RESOLVE | ASK_PROGRESS
    intern_id: int
    alert_id: Optional[int] = None
    expected_version: Optional[int] = None  # 乐观锁版本号


@router.get("/dashboard")
async def mentor_dashboard(mentor_id: Optional[int] = 1, db: Session = Depends(get_db)):
    """
    导师看板 — 冷热分离展示所有带教实习生
    热区: 有活跃预警的实习生（需立即关注）
    冷区: 正常进展的实习生
    """
    # 获取该导师的所有实习生
    interns = db.execute(
        select(Intern).where(Intern.mentor_id == mentor_id).order_by(Intern.id)
    ).scalars().all()

    hot_list = []   # 有预警/风险的
    cold_list = []  # 正常/绩优的

    for intern in interns:
        # 查找活跃预警
        alert = db.execute(
            select(MentorAlert).where(
                MentorAlert.mentor_id == mentor_id,
                MentorAlert.intern_id == intern.id,
                MentorAlert.status == AlertStatus.ACTIVE
            ).limit(1)
        ).scalars().first()

        # 当前阶段进度
        current_phase = db.execute(
            select(GrowthMap).where(
                GrowthMap.intern_id == intern.id,
                GrowthMap.status.in_(["in_progress", "pending"])
            ).order_by(GrowthMap.phase_order).limit(1)
        ).scalars().first()

        phase_tasks_done = 0
        phase_tasks_total = 0
        if current_phase:
            phase_tasks_total = db.scalar(
                select(sa_func.count()).where(GrowthTask.map_id == current_phase.id).select_from(GrowthTask)
            ) or 0
            phase_tasks_done = db.scalar(
                select(sa_func.count()).where(GrowthTask.map_id == current_phase.id, GrowthTask.status == "done").select_from(GrowthTask)
            ) or 0

        # 最近绩效快照
        latest_snap = None
        if intern.job_family == JobFamily.RD:
            latest_snap = db.execute(
                select(RDSnapshot).where(RDSnapshot.intern_id == intern.id)
                .order_by(RDSnapshot.snapshot_date.desc()).limit(1)
            ).scalars().first()
            snap_data = {
                "commits": latest_snap.commit_count if latest_snap else 0,
                "prs": latest_snap.pr_merged_count if latest_snap else 0,
                "bugs": latest_snap.bug_resolved_count if latest_snap else 0,
            }
        elif intern.job_family == JobFamily.SALES:
            latest_snap = db.execute(
                select(SalesSnapshot).where(SalesSnapshot.intern_id == intern.id)
                .order_by(SalesSnapshot.snapshot_date.desc()).limit(1)
            ).scalars().first()
            snap_data = {
                "leadsTouched": latest_snap.crm_leads_touched if latest_snap else 0,
                "callDurationMin": round(latest_snap.effective_call_duration / 60, 1) if latest_snap else 0,
            }
        else:
            snap_data = {}

        intern_card = {
            "id": intern.id,
            "name": intern.name,
            "jobFamily": intern.job_family.value,
            "currentState": intern.current_state.value,
            "stateLabel": _state_label(intern.current_state),
            "recruiterTag": intern.recruiter_tag.value,
            "entryDate": str(intern.entry_date),
            "currentPhase": current_phase.phase_name[:15] + "..." if current_phase and len(current_phase.phase_name) > 15 else (current_phase.phase_name if current_phase else ""),
            "phaseProgress": f"{phase_tasks_done}/{phase_tasks_total}",
            "phasePercent": round(phase_tasks_done / phase_tasks_total * 100) if phase_tasks_total > 0 else 0,
            "alert": {
                "id": alert.id,
                "level": alert.alert_level.value,
                "cheatSheet": alert.cheat_sheet_text,
                "version": alert.version,
            } if alert else None,
            **snap_data,
        }

        if alert or intern.recruiter_tag == RecruiterTag.RISK:
            hot_list.append(intern_card)
        else:
            cold_list.append(intern_card)

    return {"hotList": hot_list, "coldList": cold_list}


@router.post("/action")
async def mentor_action(req: ActionRequest, db: Session = Depends(get_db)):
    """
    导师一键决策操作（新工作流：不阻塞，自愿记录得积分）

    RESOLVE: 一键知晓，关闭红点（不强制填写带教内容）
    PUSH_DOC / CREATE_GROUP: 辅助操作
    """
    intern = db.get(Intern, req.intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")

    if req.action == "RESOLVE":
        if req.alert_id:
            # 关闭预警 + 乐观锁
            alert = db.get(MentorAlert, req.alert_id)
            if not alert:
                raise HTTPException(status_code=404, detail="预警不存在")
            if req.expected_version is not None and alert.version != req.expected_version:
                raise HTTPException(status_code=409, detail="version mismatch")
            alert.status = AlertStatus.RESOLVED
            alert.version += 1
            alert.resolved_at = datetime.now()
            ConcurrencySafeSession.safe_commit(db)
            return {"success": True, "message": f"已阅知晓，红点已消除（可自愿记录带教要点获取绩效积分）",
                    "new_version": alert.version}
        else:
            if intern.recruiter_tag == RecruiterTag.RISK:
                intern.recruiter_tag = RecruiterTag.STEADY
                ConcurrencySafeSession.safe_commit(db)
                return {"success": True, "message": f"已确认{intern.name}状态恢复正常，移除风险标记"}
            return {"success": True, "message": f"已确认{intern.name}状态无异常"}

    elif req.action == "ASK_PROGRESS":
        return {"success": True, "message": f"已向 {intern.name} 发送进度问询消息", "internName": intern.name}

    elif req.action in ("PUSH_DOC", "CREATE_GROUP"):
        action_desc = {"PUSH_DOC": "已推送学习资料", "CREATE_GROUP": "已创建专项沟通群"}
        return {"success": True, "message": f"{action_desc.get(req.action, req.action)}给 {intern.name}"}

    raise HTTPException(status_code=400, detail="无效的操作")


@router.post("/ask-progress/{intern_id}")
async def ask_progress(intern_id: int, db: Session = Depends(get_db)):
    """一键问进度"""
    intern = db.get(Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")
    return {"success": True, "message": f"已向 {intern.name} 发送进度问询"}


@router.put("/mark-acknowledged/{alert_id}")
async def mark_acknowledged(alert_id: int, db: Session = Depends(get_db)):
    """标记预警已知晓"""
    alert = db.get(MentorAlert, alert_id)
    if not alert or alert.status != AlertStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="预警不存在或已处理")
    from datetime import datetime
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now()
    db.commit()
    return {"success": True, "message": "已标记知晓并关闭预警"}


def _state_label(s: StateNode) -> str:
    return {StateNode.ONBOARDING: "融入期", StateNode.RAMP_UP: "上手期", StateNode.INDEPENDENT: "独立期"}.get(s, s.value)


# ============================================================
# 举证式消红点 — 绩效利益捆绑
# ============================================================

class ResolveWithEvidenceRequest(BaseModel):
    alert_id: int
    mentor_id: int = 1
    evidence_type: str = "TEXT"  # TEXT | VOICE
    evidence_content: str


@router.post("/resolve-with-evidence")
async def resolve_with_evidence(req: ResolveWithEvidenceRequest, db: Session = Depends(get_db)):
    """
    自愿记录带教要点 — 非强制，可得绩效积分（新工作流）
    
    导师选择记录时调用此接口，AI润色后写入绩效素材库
    """
    alert = db.get(MentorAlert, req.alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    if alert.mentor_id != req.mentor_id:
        raise HTTPException(status_code=403, detail="无权操作此预警")

    evidence = (req.evidence_content or "").strip()
    if not evidence:
        raise HTTPException(status_code=400, detail="请输入带教要点")

    # 生成绩效素材（AI仅润色）
    mentor_name = getattr(db.get(Mentor, req.mentor_id), 'name', '导师')
    intern_name = getattr(db.get(Intern, alert.intern_id), 'name', '实习生')
    performance_summary = _generate_performance_summary(
        mentor_name=mentor_name, intern_name=intern_name,
        evidence=evidence, alert_level=alert.alert_level.value,
    )

    # 写入绩效素材表
    log = MentorContributionLog(
        mentor_id=req.mentor_id, intern_id=alert.intern_id,
        alert_id=req.alert_id, raw_input=evidence,
        performance_summary=performance_summary,
    )
    db.add(log)

    # 若预警尚未关闭，一并关闭
    if alert.status != AlertStatus.RESOLVED:
        alert.status = AlertStatus.RESOLVED
        alert.version += 1
        alert.resolved_at = datetime.now()

    ConcurrencySafeSession.safe_commit(db)

    return {
        "success": True,
        "message": "带教记录已保存，绩效素材已写入素材库 🏆",
        "performance_summary": performance_summary,
        "alert_id": req.alert_id,
    }


def _generate_performance_summary(mentor_name: str, intern_name: str, evidence: str, alert_level: str) -> str:
    """
    生成组织建设贡献描述（写入导师绩效素材库）
    实际生产环境应调用混元 API，此处为模拟实现
    """
    # 模拟混元生成的绩效素材
    templates = {
        "RED": (
            f"【组织建设贡献】{mentor_name} 在带教过程中展现出高度责任心：\n"
            f"针对 {intern_name} 出现的严重卡点问题，{mentor_name} 及时进行了一对一辅导，\n"
            f"具体带教内容：「{evidence}」\n"
            f"该辅导帮助实习生快速定位问题根因，体现了导师在技术传承与团队建设方面的积极投入，\n"
            f"建议在本季度绩效评估中予以认可。"
        ),
        "YELLOW": (
            f"【组织建设贡献】{mentor_name} 积极参与新人培养：\n"
            f"在 {intern_name} 的上手期关键节点，{mentor_name} 主动提供技术指导与资源支持，\n"
            f"带教记录：「{evidence}」\n"
            f"该行为有效促进了新人的融入与成长，符合公司导师制的价值导向。"
        ),
    }
    return templates.get(alert_level, templates["YELLOW"])
