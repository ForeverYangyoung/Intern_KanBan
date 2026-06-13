"""
AI 服务 API 路由 — 统一管理所有 AI 能力的对外接口
对接腾讯混元大模型
"""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.dependencies import get_db
from app.models.database import (
    Intern, RDSnapshot, SalesSnapshot,
    ConsistencyCheck, MentorAlert
)
from app.services.ai_service import hunyuan_service
from app.services.state_machine import StateMachine

router = APIRouter()


@router.get("/recommendations")
async def get_recommendations(
    intern_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    获取 AI 智能推荐内容
    根据实习生当前卡点，定向匹配学习资源
    """
    if intern_id:
        intern = db.get(Intern, intern_id)
    else:
        intern = db.execute(select(Intern).limit(1)).scalars().first()

    if not intern:
        return {"recommendations": []}

    # 获取当前任务列表
    tasks = _get_current_tasks(intern)

    recommendations = await hunyuan_service.get_daily_recommendations(
        tasks, []
    )

    return {
        "intern_id": intern.id if intern else None,
        "recommendations": recommendations or [
            {
                "id": 1, "type": "case", "tag": "优秀案例",
                "title": "同岗位优秀交付物参考",
                "desc": "与你当前阶段匹配的标杆案例"
            }
        ]
    }


@router.post("/analyze-snapshots")
async def analyze_snapshots(
    intern_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    触发 AI 对多源采集数据进行分析
    核心入口：CR 审计 + 一致性校验 + 带教小抄生成
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
            # 获取研发快照
            rd_snapshot = db.execute(
                select(RDSnapshot).where(
                    RDSnapshot.intern_id == intern.id
                ).order_by(RDSnapshot.snapshot_date.desc())
            ).scalars().first()

            if rd_snapshot and rd_snapshot.raw_cr_log:
                # 1. CR 质量审计
                cr_audit = await hunyuan_service.audit_gongfeng_cr(
                    rd_snapshot.raw_cr_log
                )
                result["cr_audit"] = cr_audit

                # 如果检测到重复犯错或架构问题，生成预警
                if cr_audit.get("has_repeated_mistakes") or \
                   cr_audit.get("has_architecture_issue"):
                    risk_reason = (
                        f"技术卡点：{cr_audit.get('repeated_topic', '未知')}，"
                        f"已重复 {cr_audit.get('repeat_count', 0)} 次"
                    )
                    cheat_sheet = await hunyuan_service.generate_cheat_sheet(
                        intern.name, intern.job_family.value,
                        risk_reason,
                        {"cr_audit": cr_audit}
                    )
                    sm.create_alert(
                        intern.mentor_id, intern.id,
                        __import__('app.models.database', fromlist=['AlertLevel']).AlertLevel.RED,
                        cheat_sheet
                    )
                    result["alert_created"] = True

        elif intern.job_family.value == "SALES":
            # 销售线：审计跟进质量
            sales_snapshot = db.execute(
                select(SalesSnapshot).where(
                    SalesSnapshot.intern_id == intern.id
                ).order_by(SalesSnapshot.snapshot_date.desc())
            ).scalars().first()

            if sales_snapshot and sales_snapshot.raw_followup_summaries:
                audit = await hunyuan_service.audit_sales_followup(
                    sales_snapshot.raw_followup_summaries
                )
                result["sales_audit"] = audit

        # 2. 风险检测
        risk_info = sm.detect_risk(intern.id)
        result["risk_check"] = risk_info

        results.append(result)

    return {
        "success": True,
        "message": "AI 数据解析完成",
        "analyzed_count": len(results),
        "results": results
    }


@router.post("/consistency-check/{intern_id}")
async def consistency_check(
    intern_id: int,
    reported_text: str = Query("", description="实习生手写的日报/周报文本"),
    db: Session = Depends(get_db)
):
    """
    双向一致性校验（防反向 AI 作弊侦探）
    对比实习生手写日报与系统行为日志
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"success": False, "message": "实习生不存在"}

    # 收集系统行为日志
    behavior_log = {}
    if intern.job_family.value == "RD":
        rd_snapshot = db.execute(
            select(RDSnapshot).where(
                RDSnapshot.intern_id == intern_id
            ).order_by(RDSnapshot.snapshot_date.desc())
        ).scalars().first()
        if rd_snapshot:
            behavior_log = {
                "commits": rd_snapshot.commit_count,
                "pr_merged": rd_snapshot.pr_merged_count,
                "bugs_resolved": rd_snapshot.bug_resolved_count,
                "cr_comments": rd_snapshot.cr_total_comments
            }
    elif intern.job_family.value == "SALES":
        sales_snapshot = db.execute(
            select(SalesSnapshot).where(
                SalesSnapshot.intern_id == intern_id
            ).order_by(SalesSnapshot.snapshot_date.desc())
        ).scalars().first()
        if sales_snapshot:
            behavior_log = {
                "leads_touched": sales_snapshot.crm_leads_touched,
                "call_duration": sales_snapshot.effective_call_duration
            }

    # AI 一致性检测
    fraud_check = await hunyuan_service.detect_reporting_fraud(
        reported_text, behavior_log
    )

    # 写入一致性校验日志
    check = ConsistencyCheck(
        intern_id=intern_id,
        check_date=__import__('datetime').date.today(),
        reported_text_summary=reported_text[:500],
        actual_log_summary=str(behavior_log),
        is_conflict=fraud_check.get("is_conflict", False),
        ai_detect_insight=fraud_check.get("conflict_detail", "")
    )
    db.add(check)
    db.commit()

    return {
        "success": True,
        "intern_id": intern_id,
        "intern_name": intern.name,
        "is_conflict": fraud_check.get("is_conflict", False),
        "conflict_detail": fraud_check.get("conflict_detail", ""),
        "confidence": fraud_check.get("confidence", 0),
        "analysis": fraud_check.get("analysis", ""),
        "message": "⚠️ 检测到虚高欺骗预警！" if fraud_check.get("is_conflict")
                   else "✅ 日报与行为日志一致，未发现矛盾"
    }


@router.get("/daily-insight/{intern_id}")
async def get_daily_insight(intern_id: int, db: Session = Depends(get_db)):
    """
    获取实习生今日 AI 洞察
    根据状态机进度 + 行为数据给出个性化建议
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"error": "实习生不存在"}

    sm = StateMachine(db)
    state_info = sm.get_intern_state(intern_id)

    return {
        "intern_id": intern_id,
        "intern_name": intern.name,
        "current_state": intern.current_state.value,
        "progress": state_info.get("progress_percent", 0),
        "focus_tasks": [
            "完成当前阶段里程碑任务",
            "查看成长地图确认通关条件"
        ],
        "suggestion": (
            f"你正处于 {intern.current_state.value} 阶段，"
            f"已完成 {state_info.get('completed_count', 0)}/"
            f"{state_info.get('total_count', 0)} 个里程碑。"
            f"继续加油，通关后即可解锁下一阶段！"
        )
    }


@router.post("/generate-cheat-sheet/{intern_id}")
async def generate_cheat_sheet(intern_id: int, db: Session = Depends(get_db)):
    """
    手动触发 AI 带教小抄生成
    """
    intern = db.get(Intern, intern_id)
    if not intern:
        return {"success": False, "message": "实习生不存在"}

    sm = StateMachine(db)
    risk_info = sm.detect_risk(intern_id)
    state_info = sm.get_intern_state(intern_id)

    cheat_sheet = await hunyuan_service.generate_cheat_sheet(
        intern.name,
        intern.job_family.value,
        risk_info.get("reason", "进度正常") if risk_info else "暂无风险",
        {"state_info": state_info}
    )

    # 写入预警表
    from app.models.database import AlertLevel
    sm.create_alert(
        intern.mentor_id,
        intern_id,
        AlertLevel.YELLOW,
        cheat_sheet
    )

    return {
        "success": True,
        "intern_id": intern_id,
        "cheat_sheet": cheat_sheet
    }


def _get_current_tasks(intern) -> list:
    """获取实习生当前阶段任务标题列表"""
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
    return task_maps.get(
        (intern.job_family.value, intern.current_state.value), []
    )
