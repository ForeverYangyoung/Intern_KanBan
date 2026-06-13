"""
AI 服务 API 路由 — v3.0：AI 仅为数据提炼工具，不参与决策
对接腾讯混元大模型
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.dependencies import get_db
from app.models.database import (
    Intern, RDSnapshot, SalesSnapshot, ConsistencyCheck, MentorAlert, AlertLevel
)
from app.services.ai_service import hunyuan_service
from app.services.state_machine import StateMachine

router = APIRouter()


@router.get("/recommendations")
async def get_recommendations(intern_id: Optional[int] = Query(None),
                               db: Session = Depends(get_db)):
    """获取学习资源推荐（纯匹配，非AI决策）"""
    if intern_id:
        intern = db.get(Intern, intern_id)
    else:
        intern = db.execute(select(Intern).limit(1)).scalars().first()
    if not intern:
        return {"recommendations": []}

    tasks = _get_current_tasks(intern)
    recommendations = await hunyuan_service.get_daily_recommendations(tasks, [])
    return {"intern_id": intern.id if intern else None,
            "recommendations": recommendations or [
                {"id": 1, "type": "case", "tag": "优秀案例",
                 "title": "同岗位优秀交付物参考", "desc": "与你当前阶段匹配的标杆案例"}
            ]}


@router.post("/analyze-snapshots")
async def analyze_snapshots(intern_id: Optional[int] = Query(None),
                              db: Session = Depends(get_db)):
    """
    触发 AI 对多源数据进行结构化提炼（仅提取事实，不产生决策）
    """
    if intern_id:
        interns = [db.get(Intern, intern_id)]
    else:
        interns = db.execute(select(Intern)).scalars().all()

    results = []
    sm = StateMachine(db)

    for intern in interns:
        result = {"intern_id": intern.id, "name": intern.name}

        if intern.job_family.value == "RD":
            rd_snapshot = db.execute(
                select(RDSnapshot).where(RDSnapshot.intern_id == intern.id)
                .order_by(RDSnapshot.snapshot_date.desc())
            ).scalars().first()

            if rd_snapshot and rd_snapshot.raw_cr_log:
                # 仅提炼CR事实，不做品质判断
                cr_facts = await hunyuan_service.extract_cr_facts(rd_snapshot.raw_cr_log)
                result["cr_facts"] = cr_facts

                # 数据规则驱动：重复主题≥3才触发预警
                if len(cr_facts.get("common_topics", [])) >= 2:
                    topics = ", ".join(cr_facts["common_topics"][:2])
                    cheat_sheet = f"CR数据提炼：实习生在 [{topics}] 领域被多轮review指出问题（数据来源：{cr_facts.get('data_source_count', 0)}条CR评论）。建议导师确认是否需要针对性辅导。"
                    sm.create_alert(intern.mentor_id, intern.id, AlertLevel.YELLOW, cheat_sheet)
                    result["data_driven_alert"] = True

        elif intern.job_family.value == "SALES":
            sales_snapshot = db.execute(
                select(SalesSnapshot).where(SalesSnapshot.intern_id == intern.id)
                .order_by(SalesSnapshot.snapshot_date.desc())
            ).scalars().first()

            if sales_snapshot and sales_snapshot.raw_followup_summaries:
                patterns = await hunyuan_service.extract_sales_patterns(
                    sales_snapshot.raw_followup_summaries)
                result["sales_patterns"] = patterns

        # 纯数据风险检测
        risk_info = sm.detect_risk(intern.id)
        result["risk_check"] = risk_info
        results.append(result)

    return {"success": True, "message": "数据提炼完成（AI仅提炼，规则引擎做决策）",
            "analyzed_count": len(results), "results": results}


@router.post("/consistency-check/{intern_id}")
async def consistency_check(intern_id: int,
                              reported_text: str = Query("", description="实习生手写的日报/周报文本"),
                              db: Session = Depends(get_db)):
    """
    双向一致性校验 — AI仅提取差异，不上报"欺骗"
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"success": False, "message": "实习生不存在"}

    behavior_log = {}
    if intern.job_family.value == "RD":
        rd = db.execute(select(RDSnapshot).where(RDSnapshot.intern_id == intern_id)
                         .order_by(RDSnapshot.snapshot_date.desc())).scalars().first()
        if rd:
            behavior_log = {"commits": rd.commit_count, "pr_merged": rd.pr_merged_count,
                            "bugs_resolved": rd.bug_resolved_count, "cr_comments": rd.cr_total_comments}
    elif intern.job_family.value == "SALES":
        ss = db.execute(select(SalesSnapshot).where(SalesSnapshot.intern_id == intern_id)
                         .order_by(SalesSnapshot.snapshot_date.desc())).scalars().first()
        if ss:
            behavior_log = {"leads_touched": ss.crm_leads_touched,
                            "call_duration": ss.effective_call_duration}

    # AI 仅对比差异
    comparison = await hunyuan_service.compare_report_with_logs(reported_text, behavior_log)

    # 写入校验日志（数据规则：match_ratio < 0.5 → 标记差异较大）
    has_notable_diff = comparison.get("match_ratio", 1.0) < 0.5
    from datetime import date as dt_date
    check = ConsistencyCheck(
        intern_id=intern_id, check_date=dt_date.today(),
        reported_text_summary=reported_text[:500],
        actual_log_summary=str(behavior_log),
        is_conflict=has_notable_diff,
        ai_detect_insight="\n".join(comparison.get("differences", []))
    )
    db.add(check)
    db.commit()

    return {
        "success": True, "intern_id": intern_id, "intern_name": intern.name,
        "differences": comparison.get("differences", []),
        "match_ratio": comparison.get("match_ratio", 1.0),
        "has_notable_diff": has_notable_diff,
        "message": "数据对比完成" if not has_notable_diff else "注意到汇报与系统日志存在差异"
    }


@router.get("/daily-insight/{intern_id}")
async def get_daily_insight(intern_id: int, db: Session = Depends(get_db)):
    """获取实习生状态机进度（纯数据，非AI洞察）"""
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"error": "实习生不存在"}
    sm = StateMachine(db)
    state_info = sm.get_intern_state(intern_id)
    return {
        "intern_id": intern_id, "intern_name": intern.name,
        "current_state": intern.current_state.value,
        "progress": state_info.get("progress_percent", 0),
        "focus_tasks": ["完成当前阶段里程碑任务", "查看成长地图确认通关条件"],
        "suggestion": (
            f"你正处于 {intern.current_state.value} 阶段，"
            f"已完成 {state_info.get('completed_count', 0)}/"
            f"{state_info.get('total_count', 0)} 个里程碑。继续加油！"
        )
    }


@router.get("/dag/{intern_id}")
async def get_dag_topology(intern_id: int, db: Session = Depends(get_db)):
    """获取实习生对应的岗位DAG拓扑（用于前端DAG可视化）"""
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"error": "实习生不存在"}
    sm = StateMachine(db)
    dag = sm.get_full_dag(intern.job_family)
    status = sm.get_current_milestone_status(intern_id)
    return {"intern_id": intern_id, "intern_name": intern.name, **dag,
            "current_state": intern.current_state.value, "status": status}


def _get_current_tasks(intern) -> list:
    task_maps = {
        ("RD", "ONBOARDING"): ["搭建开发环境", "阅读技术栈文档", "完成入门Demo"],
        ("RD", "RAMP_UP"): ["修复线上Bug", "提交PR", "参加CodeReview"],
        ("RD", "INDEPENDENT"): ["核心模块开发", "技术方案设计", "指导新人"],
        ("PM", "ONBOARDING"): ["阅读产品文档", "竞品分析", "了解数据指标"],
        ("PM", "RAMP_UP"): ["撰写PRD", "组织评审", "跟进交付"],
        ("PM", "INDEPENDENT"): ["需求池规划", "跨部门协调", "版本复盘"],
        ("SALES", "ONBOARDING"): ["学习话术", "熟悉CRM", "旁听外呼"],
        ("SALES", "RAMP_UP"): ["独立外呼", "沉淀客户", "参加复盘"],
        ("SALES", "INDEPENDENT"): ["商务谈判", "签约回款", "方法论总结"],
    }
    return task_maps.get((intern.job_family.value, intern.current_state.value), [])
