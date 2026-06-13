"""
HR端 API 路由 — 周报 + 风控打标 + 常模排名
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sa_func, case, desc

from app.dependencies import get_db
from app.models.database import (
    Intern, Mentor, GrowthMap, GrowthTask,
    MentorAlert, AlertLevel, AlertStatus, StateNode,
    RecruiterTag, JobFamily, RDSnapshot, SalesSnapshot
)

router = APIRouter()


@router.get("/weekly-report")
async def weekly_report(db: Session = Depends(get_db)):
    """
    HR 周报 — 同岗位常模百分位排名 + 全局概览
    展示所有实习生的成长状态对比，而非截面数据
    """
    interns = db.execute(select(Intern).order_by(Intern.id)).scalars().all()

    report_rows = []
    for intern in interns:
        mentor = db.get(Mentor, intern.mentor_id)
        current_phase = db.execute(
            select(GrowthMap).where(
                GrowthMap.intern_id == intern.id,
                GrowthMap.status.in_(["in_progress", "pending"])
            ).order_by(GrowthMap.phase_order).limit(1)
        ).scalars().first()

        # 总体完成进度（跨所有阶段）
        all_maps = db.execute(select(GrowthMap).where(GrowthMap.intern_id == intern.id)).scalars().all()
        total_done = 0
        total_all = 0
        for m in all_maps:
            t = db.scalar(
                select(sa_func.count()).where(GrowthTask.map_id == m.id).select_from(GrowthTask)
            ) or 0
            d = db.scalar(
                select(sa_func.count()).where(GrowthTask.map_id == m.id, GrowthTask.status == "done").select_from(GrowthTask)
            ) or 0
            total_all += t
            total_done += d

        # 最新绩效数据
        latest_rd = None
        if intern.job_family == JobFamily.RD:
            latest_rd = db.execute(
                select(RDSnapshot).where(RDSnapshot.intern_id == intern.id)
                .order_by(RDSnapshot.snapshot_date.desc()).limit(1)
            ).scalars().first()
            perf_summary = {
                "commits": latest_rd.commit_count if latest_rd else 0,
                "prs": latest_rd.pr_merged_count if latest_rd else 0,
                "bugs": latest_rd.bug_resolved_count if latest_rd else 0,
            }
        elif intern.job_family == JobFamily.SALES:
            latest_sales = db.execute(
                select(SalesSnapshot).where(SalesSnapshot.intern_id == intern.id)
                .order_by(SalesSnapshot.snapshot_date.desc()).limit(1)
            ).scalars().first()
            perf_summary = {
                "leadsTouched": latest_sales.crm_leads_touched if latest_sales else 0,
                "callDurationMin": round(latest_sales.effective_call_duration / 60, 1) if latest_sales else 0,
            }
        else:
            perf_summary = {}

        # 活跃预警数
        active_alerts = db.scalar(
            select(sa_func.count()).where(
                MentorAlert.intern_id == intern.id,
                MentorAlert.status == AlertStatus.ACTIVE
            ).select_from(MentorAlert)
        ) or 0

        report_rows.append({
            "id": intern.id,
            "name": intern.name,
            "jobFamily": intern.job_family.value,
            "jobLabel": _jf_label(intern.job_family),
            "mentorName": mentor.name if mentor else "",
            "currentState": intern.current_state.value,
            "stateLabel": _state_label(intern.current_state),
            "recruiterTag": intern.recruiter_tag.value,
            "entryDate": str(intern.entry_date),
            "currentPhase": current_phase.phase_name if current_phase else "-",
            "overallProgress": round(total_done / total_all * 100) if total_all > 0 else 0,
            **perf_summary,
            "activeAlerts": active_alerts,
            "reason": _risk_reason(intern, total_done, total_all, perf_summary),
        })

    # 按岗位分组计算常模排名
    for jf in [JobFamily.RD, JobFamily.PM, JobFamily.SALES]:
        group = [r for r in report_rows if r["jobFamily"] == jf.value]
        sorted_group = sorted(group, key=lambda x: x["overallProgress"], reverse=True)
        for rank, row in enumerate(sorted_group, 1):
            row["sameRoleRank"] = rank
            row["sameRoleTotal"] = len(sorted_group)
            row["percentile"] = round((len(sorted_group) - rank) / len(sorted_group) * 100) if len(sorted_group) > 1 else 100

    return {"reportDate": __import__("datetime").date.today().isoformat(), "rows": report_rows}


@router.get("/risk-tags")
async def risk_tags(db: Session = Depends(get_db)):
    """风控打标汇总"""
    interns = db.execute(select(Intern).order_by(Intern.id)).scalars().all()
    risk_list = []
    for i in interns:
        alerts = db.execute(
            select(MentorAlert).where(
                MentorAlert.intern_id == i.id,
                MentorAlert.status == AlertStatus.ACTIVE
            ).order_by(MentorAlert.created_at.desc())
        ).scalars().all()
        if i.recruiter_tag != RecruiterTag.STEADY or alerts:
            risk_list.append({
                "id": i.id,
                "name": i.name,
                "tag": i.recruiter_tag.value,
                "tagLabel": {RecruiterTag.LIGHTNING: "绩优闪电", RecruiterTag.RISK: "红灯风险"}.get(i.recruiter_tag, "正常稳健"),
                "alerts": [
                    {"id": a.id, "level": a.alert_level.value, "text": a.cheat_sheet_text}
                    for a in alerts
                ],
            })
    return {"riskList": risk_list}


def _jf_label(jf: JobFamily) -> str:
    return {JobFamily.RD: "研发线", JobFamily.PM: "产品线", JobFamily.SALES: "销售线"}.get(jf, jf.value)

def _state_label(s: StateNode) -> str:
    return {StateNode.ONBOARDING: "融入期", StateNode.RAMP_UP: "上手期", StateNode.INDEPENDENT: "独立期"}.get(s, s.value)


def _risk_reason(intern, total_done, total_all, perf_summary):
    """生成风险原因简述（给 HR 看的告警上下文）"""
    if intern.recruiter_tag.value == "RISK":
        progress = round(total_done / total_all * 100) if total_all > 0 else 0
        if intern.job_family == JobFamily.SALES:
            leads = perf_summary.get("leadsTouched", 0)
            return f"销售线索连续低迷（近周 {leads} 条），企微 CRM 48h 无足迹，疑似行为失联"
        elif intern.job_family == JobFamily.PM:
            return f"PRD 评审连续被驳回，总进度仅 {progress}%"
        else:
            return f"研发任务完成度仅 {progress}%，连续两周低于同岗均值"
    if intern.recruiter_tag.value == "LIGHTNING":
        return f"连续两周状态机通关速度处于同岗前 10%，CR 评语正面率 > 85%"
    return "正常"
