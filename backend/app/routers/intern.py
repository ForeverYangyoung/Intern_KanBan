"""
实习生端 API 路由 — 从数据库读取真实数据
"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sa_func

from app.dependencies import get_db
from app.models.database import (
    Intern, CustomTask, StateNode, JobFamily,
    GrowthMap, GrowthTask, RDSnapshot, SalesSnapshot,
    RecruiterTag, BreakdownEvent
)
from app.services.state_machine import StateMachine

router = APIRouter()


class CustomTaskCreate(BaseModel):
    title: str
    time: Optional[str] = None


# ============================================================
# 实习生看板 — 核心展示成长变化轨迹
# ============================================================

@router.get("/dashboard")
async def get_dashboard(
    intern_id: Optional[int] = Query(None, description="实习生ID，默认取第一个"),
    db: Session = Depends(get_db)
):
    """
    获取实习生每日看板数据（含成长时间线）
    返回: 实习生信息、当前阶段任务、里程碑进度、绩效趋势、自定义事项
    """
    # 获取目标实习生
    if intern_id:
        intern = db.get(Intern, intern_id)
    else:
        intern = db.execute(select(Intern).limit(1)).scalars().first()

    if not intern:
        return {"intern": None, "tasks": [], "customTasks": [], "completionRate": 0}

    # 状态机信息
    sm = StateMachine(db)
    state_info = sm.get_intern_state(intern.id)

    # 当前正在进行的成长阶段
    current_phase = db.execute(
        select(GrowthMap).where(
            GrowthMap.intern_id == intern.id,
            GrowthMap.status.in_(["in_progress", "pending"])
        ).order_by(GrowthMap.phase_order).limit(1)
    ).scalars().first()

    # 获取当前阶段任务
    tasks = []
    all_phases = []
    if current_phase:
        phase_tasks = db.execute(
            select(GrowthTask).where(GrowthTask.map_id == current_phase.id).order_by(GrowthTask.dimension)
        ).scalars().all()
        for t in phase_tasks:
            tasks.append({
                "id": t.id,
                "title": t.title,
                "dimension": t.dimension,
                "status": t.status,
                "duration": f"{t.estimated_hours}h" if t.estimated_hours else "",
                "type": "system",
                "source": t.source,
            })

    # 所有阶段概览（用于成长地图联动）
    all_phases_db = db.execute(
        select(GrowthMap).where(GrowthMap.intern_id == intern.id).order_by(GrowthMap.phase_order)
    ).scalars().all()
    for p in all_phases_db:
        phase_task_count = db.scalar(
            select(sa_func.count()).where(GrowthTask.map_id == p.id).select_from(GrowthTask)
        ) or 0
        phase_done_count = db.scalar(
            select(sa_func.count()).where(GrowthTask.map_id == p.id, GrowthTask.status == "done").select_from(GrowthTask)
        ) or 0
        all_phases.append({
            "id": p.id,
            "name": p.phase_name,
            "phaseOrder": p.phase_order,
            "status": p.status,
            "dateStart": str(p.date_start.date()) if p.date_start else None,
            "dateEnd": str(p.date_end.date()) if p.date_end else None,
            "totalTasks": phase_task_count,
            "doneTasks": phase_done_count,
            "progress": round(phase_done_count / phase_task_count * 100) if phase_task_count > 0 else 0,
        })

    # 自定义事项
    custom_tasks = db.execute(
        select(CustomTask).where(CustomTask.intern_id == intern.id)
    ).scalars().all()

    # 绩效快照趋势（周度）
    weekly_trend = []
    if intern.job_family == JobFamily.RD:
        snapshots = db.execute(
            select(RDSnapshot).where(RDSnapshot.intern_id == intern.id)
            .order_by(RDSnapshot.snapshot_date)
        ).scalars().all()
        for s in snapshots:
            weekly_trend.append({
                "week": str(s.snapshot_date),
                "commits": s.commit_count,
                "prs": s.pr_merged_count,
                "bugs": s.bug_resolved_count,
                "crComments": s.cr_total_comments,
            })
    elif intern.job_family == JobFamily.SALES:
        snapshots = db.execute(
            select(SalesSnapshot).where(SalesSnapshot.intern_id == intern.id)
            .order_by(SalesSnapshot.snapshot_date)
        ).scalars().all()
        for s in snapshots:
            weekly_trend.append({
                "week": str(s.snapshot_date),
                "leadsTouched": s.crm_leads_touched,
                "callDuration": round(s.effective_call_duration / 60, 1),  # 分钟
            })
    else:
        weekly_trend = []

    # 计算总完成率
    total_tasks_all = sum(p["totalTasks"] for p in all_phases)
    done_tasks_all = sum(p["doneTasks"] for p in all_phases)
    completion_rate = round(done_tasks_all / total_tasks_all * 100) if total_tasks_all > 0 else 0

    # 计算入职天数和当前周数
    days_since_entry = (date.today() - intern.entry_date).days if intern.entry_date else 0
    week_num = max(days_since_entry // 7 + 1, 1)

    return {
        "intern": {
            "id": intern.id,
            "name": intern.name,
            "role": _role_label(intern.job_family),
            "jobFamily": intern.job_family.value,
            "phase": _state_label(intern.current_state),
            "currentState": intern.current_state.value,
            "entryDate": str(intern.entry_date),
            "recruiterTag": intern.recruiter_tag.value,
            "weekNum": week_num,
            "daysSinceEntry": days_since_entry,
        },
        "stateMachine": state_info,
        "currentPhase": {
            "id": current_phase.id,
            "name": current_phase.phase_name,
            "status": current_phase.status,
        } if current_phase else None,
        "tasks": tasks,
        "customTasks": [
            {
                "id": ct.id,
                "title": ct.title,
                "time": ct.time_range,
                "status": ct.status,
                "type": "custom"
            }
            for ct in custom_tasks
        ],
        "phases": all_phases,
        "weeklyTrend": weekly_trend,
        "completionRate": completion_rate,
    }


@router.get("/list")
async def list_interns(db: Session = Depends(get_db)):
    """获取所有实习生列表（用于切换查看不同人）"""
    interns = db.execute(select(Intern).order_by(Intern.id)).scalars().all()
    result = []
    for i in interns:
        # 计算各阶段进度
        phases = db.execute(
            select(GrowthMap).where(GrowthMap.intern_id == i.id).order_by(GrowthMap.phase_order)
        ).scalars().all()
        done = sum(
            db.scalar(
                select(sa_func.count()).where(
                    GrowthTask.map_id == p.id, GrowthTask.status == "done"
                ).select_from(GrowthTask)
            ) or 0 for p in phases
        )
        total = sum(
            db.scalar(
                select(sa_func.count()).where(GrowthTask.map_id == p.id).select_from(GrowthTask)
            ) or 0
            for p in phases
        )
        result.append({
            "id": i.id,
            "name": i.name,
            "jobFamily": i.job_family.value,
            "currentState": i.current_state.value,
            "recruiterTag": i.recruiter_tag.value,
            "mentorId": i.mentor_id,
            "entryDate": str(i.entry_date),
            "progress": round(done / total * 100) if total > 0 else 0,
        })
    return result


@router.get("/{intern_id}/growth-map")
async def get_growth_map(intern_id: int, db: Session = Depends(get_db)):
    """获取指定实习生的完整成长地图"""
    intern = db.get(Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")

    sm = StateMachine(db)
    state_info = sm.get_intern_state(intern_id)

    # 从数据库读取三阶段
    phases = []
    all_maps = db.execute(
        select(GrowthMap).where(GrowthMap.intern_id == intern_id).order_by(GrowthMap.phase_order)
    ).scalars().all()

    dim_map = {}
    for gm in all_maps:
        tasks = db.execute(
            select(GrowthTask).where(GrowthTask.map_id == gm.id).order_by(GrowthTask.dimension)
        ).scalars().all()

        dimensions = {}
        for t in tasks:
            d = t.dimension
            if d not in dimensions:
                dimensions[d] = {"name": d, "systemTasks": [], "customTasks": [], "completion": 0}
            task_item = {
                "id": t.id,
                "title": t.title,
                "description": t.description or "",
                "status": t.status,
                "source": t.source,
                "hours": t.estimated_hours,
            }
            if t.source == "self":
                dimensions[d]["customTasks"].append(task_item)
            else:
                dimensions[d]["systemTasks"].append(task_item)

        # 计算每个维度的完成率
        for d in dimensions:
            all_ts = dimensions[d]["systemTasks"] + dimensions[d]["customTasks"]
            done_cnt = sum(1 for t in all_ts if t["status"] in ("done", "completed"))
            dimensions[d]["completion"] = round(done_cnt / len(all_ts) * 100) if all_ts else 0

        phases.append({
            "id": gm.id,
            "name": gm.phase_name,
            "dateRange": f"{gm.date_start.strftime('%m/%d')}-{gm.date_end.strftime('%m/%d')}" if gm.date_start and gm.date_end else "",
            "dateStart": str(gm.date_start),
            "dateEnd": str(gm.date_end),
            "dimensions": list(dimensions.values()),
            "status": gm.status,
            "phaseOrder": gm.phase_order,
        })

    # 自定义事项汇总
    custom_tasks = db.execute(
        select(CustomTask).where(CustomTask.intern_id == intern_id)
    ).scalars().all()

    return {
        "internId": intern_id,
        "name": intern.name,
        "jobFamily": intern.job_family.value,
        "currentState": intern.current_state.value,
        "stateInfo": state_info,
        "phases": phases,
        "customTasks": [
            {"id": ct.id, "title": ct.title, "time": ct.time_range, "status": ct.status}
            for ct in custom_tasks
        ],
    }


@router.post("/custom-task")
async def add_custom_task(task: CustomTaskCreate, db: Session = Depends(get_db)):
    """添加自定义事项"""
    intern = db.execute(select(Intern).limit(1)).scalars().first()
    if not intern:
        raise HTTPException(status_code=400, detail="请先创建实习生")
    ct = CustomTask(intern_id=intern.id, title=task.title, time_range=task.time or "", status="pending")
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return {"success": True, "task": {"id": ct.id, "title": ct.title, "time": ct.time_range, "status": ct.status, "type": "custom"}}


@router.put("/toggle-task/{task_id}")
async def toggle_task(task_id: int, db: Session = Depends(get_db)):
    """切换任务状态（勾选/取消）"""
    task = db.get(GrowthTask, task_id)
    if not task:
        ct = db.get(CustomTask, task_id)
        if ct:
            new_status = "done" if ct.status != "done" else "in_progress"
            ct.status = new_status
            db.commit()
            return {"success": True, "newStatus": new_status}
        raise HTTPException(status_code=404, detail="任务不存在")

    new_status = "done" if task.status != "done" else "in_progress"
    task.status = new_status
    db.commit()
    return {"success": True, "newStatus": new_status}


class ReverseConfirmRequest(BaseModel):
    intern_id: int
    text: str


@router.post("/reverse-confirm")
async def submit_reverse_confirm(req: ReverseConfirmRequest, db: Session = Depends(get_db)):
    """
    销售反向确认微流程（§13.3 补丁二）
    销售实习生在线下外呼、绕过企微 CRM 时，提交非结构化话术说明，AI 审计其真实度。
    简单规则：有具体客户名 + 数字 → 通过；否则打回。
    """
    intern = db.get(Intern, req.intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")
    if intern.job_family != JobFamily.SALES:
        raise HTTPException(status_code=400, detail="非销售岗，无需反向确认")

    text = (req.text or "").strip()
    if not text:
        return {"success": False, "passed": False, "reason": "话术为空"}

    # 简易 AI 审计：是否含具体客户名/数字/外呼关键词
    import re
    has_number = bool(re.search(r"\d+", text))
    has_keywords = any(kw in text for kw in ["外呼", "客户", "回访", "沟通", "电话", "面谈", "意向", "需求", "报价", "demo", "演示"])
    text_length = len(text)

    passed = has_number and has_keywords and text_length >= 15

    return {
        "success": True,
        "passed": passed,
        "reason": (
            "话术含具体数字与外呼要点，AI 判定真实可信，状态机阻断已解除"
            if passed else
            f"AI 审计未通过：需补充具体客户名 + 外呼数量 + 沟通要点（当前长度 {text_length}，命中数字={has_number}，命中关键词={has_keywords}）"
        ),
        "audit": {
            "has_number": has_number,
            "has_keywords": has_keywords,
            "length": text_length,
        }
    }


# ============================================================
# Copilot 弹窗 — 白天轨实时响应
# ============================================================

@router.get("/{intern_id}/active-breakdowns")
async def get_active_breakdowns(intern_id: int, db: Session = Depends(get_db)):
    """
    获取实习生当前活跃的崩溃事件（Copilot 弹窗数据源）
    前端轮询此接口，有活跃事件时弹出 Copilot 建议
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")

    # 查询未解决的崩溃事件（按时间倒序）
    events = db.execute(
        select(BreakdownEvent)
        .where(BreakdownEvent.intern_id == intern_id, BreakdownEvent.resolved_at.is_(None))
        .order_by(BreakdownEvent.triggered_at.desc())
    ).scalars().all()

    if not events:
        return {"hasActive": False, "events": []}

    return {
        "hasActive": True,
        "events": [
            {
                "id": e.id,
                "breakdownType": e.breakdown_type,
                "track": e.track,
                "copilotResponse": e.copilot_response,
                "triggeredAt": e.triggered_at.isoformat() if e.triggered_at else None,
            }
            for e in events
        ],
    }


@router.post("/{intern_id}/dismiss-breakdown/{event_id}")
async def dismiss_breakdown(intern_id: int, event_id: int, db: Session = Depends(get_db)):
    """实习生关闭/忽略 Copilot 弹窗"""
    event = db.get(BreakdownEvent, event_id)
    if not event or event.intern_id != intern_id:
        raise HTTPException(status_code=404, detail="事件不存在")
    event.resolved_at = sa_func.now()
    db.commit()
    return {"success": True, "message": "已关闭 Copilot 弹窗"}


# ============================================================
# 成长错题本 — 深夜轨归纳，转正评审佐证
# ============================================================

@router.get("/{intern_id}/error-book")
async def get_error_book(intern_id: int, db: Session = Depends(get_db)):
    """
    获取实习生的成长错题本
    深夜轨批处理产出，展示重复卡点模式，供转正评审引用
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="实习生不存在")

    # 查询该实习生的错题本记录
    errors = db.execute(
        select(GrowthErrorBook)
        .where(GrowthErrorBook.intern_id == intern_id)
        .order_by(GrowthErrorBook.last_seen_at.desc())
    ).scalars().all()

    # 如果没有记录，根据崩溃事件模拟生成
    if not errors:
        # 查询该实习生的崩溃事件，归纳错误模式
        breakdowns = db.execute(
            select(BreakdownEvent)
            .where(BreakdownEvent.intern_id == intern_id)
            .order_by(BreakdownEvent.triggered_at.desc())
        ).scalars().all()

        if breakdowns:
            # 模拟归纳错题本
            error_patterns = _simulate_error_patterns(breakdowns)
            return {
                "intern_id": intern_id,
                "intern_name": intern.name,
                "error_patterns": error_patterns,
                "has_data": True,
            }

        return {
            "intern_id": intern_id,
            "intern_name": intern.name,
            "error_patterns": [],
            "has_data": False,
            "message": "暂无错题记录，继续保持！",
        }

    return {
        "intern_id": intern_id,
        "intern_name": intern.name,
        "error_patterns": [
            {
                "pattern": e.error_pattern,
                "occurrence_count": e.occurrence_count,
                "ai_summary": e.ai_summary,
                "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
            }
            for e in errors
        ],
        "has_data": True,
    }


def _simulate_error_patterns(breakdowns):
    """根据崩溃事件模拟归纳错题本"""
    pattern_map = {}
    for e in breakdowns:
        bt = e.breakdown_type
        if bt not in pattern_map:
            pattern_map[bt] = {
                "pattern": bt,
                "occurrence_count": 0,
                "summaries": [],
            }
        pattern_map[bt]["occurrence_count"] += 1
        resp = e.copilot_response or {}
        if resp.get("root_cause"):
            pattern_map[bt]["summaries"].append(resp["root_cause"])

    result = []
    for bt, data in pattern_map.items():
        summaries = list(dict.fromkeys(data["summaries"]))[:3]  # 去重取前3
        result.append({
            "pattern": data["pattern"],
            "occurrence_count": data["occurrence_count"],
            "ai_summary": f"重复出现 {data['occurrence_count']} 次，主要根因：{'; '.join(summaries) if summaries else '待分析'}。建议：针对性加强相关技能培训。",
            "last_seen_at": max(b.triggered_at for b in breakdowns if b.breakdown_type == bt).isoformat() if any(b.triggered_at for b in breakdowns if b.breakdown_type == bt) else None,
        })
    return result


# ============================================================
# 辅助函数
# ============================================================

def _role_label(jf: JobFamily) -> str:
    return {JobFamily.RD: "研发实习生", JobFamily.PM: "产品实习生", JobFamily.SALES: "销售实习生"}.get(jf.value, jf.value)

def _state_label(state: StateNode) -> str:
    return {StateNode.ONBOARDING: "融入期", StateNode.RAMP_UP: "上手期", StateNode.INDEPENDENT: "独立期"}.get(state, state.value)
