"""
里程碑状态机引擎 — 核心资产
实现事件驱动的 DAG 状态流转：ONBOARDING → RAMP_UP → INDEPENDENT

核心原则：
1. 事件触发制，非时间推进制
2. 所有判断由纯数据规则驱动，AI 不参与决策
3. DAG 前置边：前驱阶段全部完成才能进入下一阶段
"""
from datetime import date, datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.database import (
    Intern, MilestoneConfig, RDSnapshot, SalesSnapshot,
    StateNode, JobFamily, RecruiterTag, MentorAlert,
    AlertLevel, AlertStatus
)

# ============================================================
# 岗位 DAG 拓扑定义
# ============================================================
STATE_ORDER = [StateNode.ONBOARDING, StateNode.RAMP_UP, StateNode.INDEPENDENT]

JOB_DAG = {
    JobFamily.RD: {
        StateNode.ONBOARDING: {
            "name": "融入期 — 环境配置与规范",
            "milestones": [
                {"id": "rd_onb_1", "name": "开发环境配置完成", "trigger": "DEV_ENV_SETUP_DONE",
                 "rule": {"field": "commit_count", "op": "gt", "value": 0}, "required": 1},
                {"id": "rd_onb_2", "name": "通过基础代码规范考核", "trigger": "CODE_STANDARD_PASSED",
                 "rule": {"field": "cr_total_comments", "op": "gt", "value": 0}, "required": 1},
            ]
        },
        StateNode.RAMP_UP: {
            "name": "上手期 — Bug修复与PR合入",
            "milestones": [
                {"id": "rd_ramp_1", "name": "独立修复首个线上Bug", "trigger": "FIRST_BUG_RESOLVED",
                 "rule": {"field": "bug_resolved_count", "op": "gt", "value": 0}, "required": 1},
                {"id": "rd_ramp_2", "name": "合入首个小需求PR", "trigger": "FIRST_PR_MERGED",
                 "rule": {"field": "pr_merged_count", "op": "gt", "value": 0}, "required": 1},
            ]
        },
        StateNode.INDEPENDENT: {
            "name": "独立期 — 模块Owner与交付保障",
            "milestones": [
                {"id": "rd_ind_1", "name": "独立Owner核心业务模块", "trigger": "MODULE_OWNERSHIP_ASSIGNED",
                 "rule": {"field": "pr_merged_count", "op": "gte", "value": 3}, "required": 1},
                {"id": "rd_ind_2", "name": "TAPD需求交付准时率达标(连续3周)", "trigger": "DELIVERY_ON_TIME_3_WEEKS",
                 "rule": {"field": "bug_resolved_count", "op": "gte", "value": 5}, "required": 1},
            ]
        },
    },
    JobFamily.PM: {
        StateNode.ONBOARDING: {
            "name": "融入期 — 产品认知与思维培养",
            "milestones": [
                {"id": "pm_onb_1", "name": "阅读产品引导文档", "trigger": "GUIDE_DOC_READ", "rule": None, "required": 1},
                {"id": "pm_onb_2", "name": "完成竞品分析思维导图", "trigger": "COMPETITOR_ANALYSIS_DONE", "rule": None, "required": 1},
            ]
        },
        StateNode.RAMP_UP: {
            "name": "上手期 — 需求分析与文档输出",
            "milestones": [
                {"id": "pm_ramp_1", "name": "输出首份完整PRD并通过评审", "trigger": "FIRST_PRD_APPROVED", "rule": None, "required": 1},
            ]
        },
        StateNode.INDEPENDENT: {
            "name": "独立期 — 需求池管理与版本规划",
            "milestones": [
                {"id": "pm_ind_1", "name": "主导核心版本迭代需求池规划", "trigger": "REQUIREMENT_POOL_OWNERSHIP", "rule": None, "required": 1},
            ]
        },
    },
    JobFamily.SALES: {
        StateNode.ONBOARDING: {
            "name": "融入期 — 话术与系统培训",
            "milestones": [
                {"id": "sales_onb_1", "name": "销售话术通关", "trigger": "SALES_SCRIPT_PASSED",
                 "rule": {"field": "effective_call_duration", "op": "gt", "value": 0}, "required": 1},
                {"id": "sales_onb_2", "name": "熟悉CRM系统操作", "trigger": "CRM_SYSTEM_FAMILIAR",
                 "rule": {"field": "crm_leads_touched", "op": "gt", "value": 0}, "required": 1},
            ]
        },
        StateNode.RAMP_UP: {
            "name": "上手期 — 独立外呼与客户沉淀",
            "milestones": [
                {"id": "sales_ramp_1", "name": "独立外呼并沉淀有效意向客户", "trigger": "CRM_FIRST_CALL",
                 "rule": {"field": "crm_leads_touched", "op": "gte", "value": 3}, "required": 1},
            ]
        },
        StateNode.INDEPENDENT: {
            "name": "独立期 — 全链路商务谈判",
            "milestones": [
                {"id": "sales_ind_1", "name": "独立完成全链路商务谈判", "trigger": "FULL_DEAL_CLOSED",
                 "rule": {"field": "crm_leads_touched", "op": "gte", "value": 10}, "required": 1},
            ]
        },
    }
}

# ============================================================
# 纯数据规则引擎
# ============================================================
def evaluate_rule(snapshot, rule: dict) -> bool:
    if not rule or not snapshot:
        return False
    field_val = getattr(snapshot, rule["field"], 0) or 0
    op, val = rule["op"], rule["value"]
    if op == "gt": return field_val > val
    if op == "gte": return field_val >= val
    if op == "lt": return field_val < val
    if op == "lte": return field_val <= val
    if op == "eq": return field_val == val
    return False

def evaluate_milestone(snapshots: list, milestone: dict) -> bool:
    rule = milestone.get("rule")
    if not rule:
        return True
    count = sum(1 for s in snapshots if evaluate_rule(s, rule))
    return count >= milestone.get("required", 1)


class StateMachine:
    """DAG 状态机 — 纯数据驱动"""

    def __init__(self, db: Session):
        self.db = db

    # ===== DAG 拓扑查询 =====
    def get_full_dag(self, job_family: JobFamily) -> dict:
        dag = JOB_DAG.get(job_family, {})
        states = []
        for i, state in enumerate(STATE_ORDER):
            node = dag.get(state, {"name": state.value, "milestones": []})
            states.append({
                "state": state.value, "name": node["name"], "order": i,
                "prerequisites": [STATE_ORDER[i-1].value] if i > 0 else [],
                "milestones": [{
                    "id": m["id"], "name": m["name"], "trigger": m["trigger"],
                    "rule": m.get("rule"), "required": m.get("required", 1)
                } for m in node["milestones"]]
            })
        return {
            "job_family": job_family.value, "states": states,
            "edges": [{"from": STATE_ORDER[i-1].value, "to": STATE_ORDER[i].value}
                      for i in range(1, len(STATE_ORDER))]
        }

    def get_current_milestone_status(self, intern_id: int) -> dict:
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return {"error": "实习生不存在"}
        node = JOB_DAG.get(intern.job_family, {}).get(intern.current_state, {"name": "", "milestones": []})
        snapshots = list(self._get_snapshots(intern_id, intern.job_family))
        milestones_detail = []
        completed = 0
        for ms in node["milestones"]:
            done = evaluate_milestone(snapshots, ms)
            if done: completed += 1
            milestones_detail.append({
                "id": ms["id"], "name": ms["name"], "trigger": ms["trigger"],
                "done": done, "rule": ms.get("rule")
            })
        return {
            "intern_id": intern_id, "current_state": intern.current_state.value,
            "stage_name": node.get("name", ""), "milestones": milestones_detail,
            "completed": completed, "total": len(node["milestones"]),
            "can_advance": completed >= len(node["milestones"])
        }

    def _get_snapshots(self, intern_id: int, job_family: JobFamily):
        if job_family == JobFamily.RD:
            return self.db.execute(
                select(RDSnapshot).where(RDSnapshot.intern_id == intern_id)
                .order_by(RDSnapshot.snapshot_date)
            ).scalars().all()
        elif job_family == JobFamily.SALES:
            return self.db.execute(
                select(SalesSnapshot).where(SalesSnapshot.intern_id == intern_id)
                .order_by(SalesSnapshot.snapshot_date)
            ).scalars().all()
        return []

    # ===== 核心事件处理 =====
    def process_rd_event(self, intern_id: int, event_type: str, event_data: dict = None) -> dict:
        return self._process_event(intern_id, event_type, JobFamily.RD)

    def process_pm_event(self, intern_id: int, event_type: str, event_data: dict = None) -> dict:
        return self._process_event(intern_id, event_type, JobFamily.PM)

    def process_sales_event(self, intern_id: int, event_type: str, event_data: dict = None) -> dict:
        return self._process_event(intern_id, event_type, JobFamily.SALES)

    def _process_event(self, intern_id: int, event_type: str, job_family: JobFamily) -> dict:
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return {"success": False, "message": f"实习生 ID {intern_id} 不存在"}

        old_state = intern.current_state
        node = JOB_DAG.get(job_family, {}).get(intern.current_state)
        if not node:
            return {"success": True, "state_changed": False, "current_state": old_state.value,
                    "message": f"当前阶段 {old_state.value} 无DAG配置"}

        snapshots = list(self._get_snapshots(intern_id, job_family))
        completed = sum(1 for ms in node["milestones"] if evaluate_milestone(snapshots, ms))
        total = len(node["milestones"])

        result = {
            "success": True, "state_changed": False, "current_state": old_state.value,
            "event": event_type, "completed_milestones": completed,
            "total_milestones": total,
            "progress_percent": round(completed / max(total, 1) * 100, 1)
        }

        if completed >= total:
            next_state = self._get_next_state(old_state)
            if next_state:
                intern.current_state = next_state
                self.db.commit()
                result["state_changed"] = True
                result["old_state"] = old_state.value
                result["current_state"] = next_state.value
                result["message"] = f"🎉 通关！从 {old_state.value} 晋升至 {next_state.value}"
                self._check_lightning_promotion(intern)
            else:
                result["message"] = f"已完成 {old_state.value} 全部里程碑，已是最终阶段"
        else:
            result["message"] = f"里程碑进度: {completed}/{total}，尚不满足通关条件"
        return result

    def _get_next_state(self, current: StateNode) -> Optional[StateNode]:
        try:
            idx = STATE_ORDER.index(current)
            return STATE_ORDER[idx + 1] if idx + 1 < len(STATE_ORDER) else None
        except ValueError:
            return None

    def _check_lightning_promotion(self, intern: Intern):
        if intern.current_state == StateNode.INDEPENDENT:
            intern.recruiter_tag = RecruiterTag.LIGHTNING
            self.db.commit()

    # ===== 状态查询 =====
    def get_intern_state(self, intern_id: int) -> dict:
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return {"success": False, "message": "实习生不存在"}
        status = self.get_current_milestone_status(intern_id)
        return {
            "intern_id": intern_id, "name": intern.name,
            "job_family": intern.job_family.value,
            "current_state": intern.current_state.value,
            "recruiter_tag": intern.recruiter_tag.value,
            "current_milestones": status.get("milestones", []),
            "completed_count": status.get("completed", 0),
            "total_count": status.get("total", 0),
            "progress_percent": round(status.get("completed", 0) / max(status.get("total", 1), 1) * 100, 1)
        }

    # ===== 预警管理 =====
    def create_alert(self, mentor_id: int, intern_id: int,
                     alert_level: AlertLevel, cheat_sheet_text: str) -> MentorAlert:
        alert = MentorAlert(mentor_id=mentor_id, intern_id=intern_id,
                            alert_level=alert_level, cheat_sheet_text=cheat_sheet_text,
                            status=AlertStatus.ACTIVE)
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_active_alerts(self, mentor_id: int) -> list:
        alerts = self.db.execute(
            select(MentorAlert).where(MentorAlert.mentor_id == mentor_id,
                                       MentorAlert.status == AlertStatus.ACTIVE)
        ).scalars().all()
        result = []
        for alert in alerts:
            intern = self.db.get(Intern, alert.intern_id)
            result.append({
                "id": alert.id, "intern_id": alert.intern_id,
                "intern_name": intern.name if intern else "未知",
                "alert_level": alert.alert_level.value,
                "cheat_sheet_text": alert.cheat_sheet_text,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat() if alert.created_at else None
            })
        return result

    def resolve_alert(self, alert_id: int) -> bool:
        alert = self.db.get(MentorAlert, alert_id)
        if alert:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            self.db.commit()
            return True
        return False

    # ===== 纯数据风险检测 =====
    def detect_risk(self, intern_id: int) -> Optional[dict]:
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return None

        if intern.current_state == StateNode.ONBOARDING and intern.entry_date:
            days = (date.today() - intern.entry_date).days
            if days > 14:
                status = self.get_current_milestone_status(intern_id)
                if status.get("completed", 0) == 0:
                    intern.recruiter_tag = RecruiterTag.RISK
                    self.db.commit()
                    return {"intern_id": intern_id, "risk_detected": True,
                            "reason": f"入职 {days} 天仍未完成任何融入期里程碑", "days_since_entry": days}

        if intern.current_state == StateNode.RAMP_UP and intern.entry_date:
            days = (date.today() - intern.entry_date).days
            if days > 35:
                status = self.get_current_milestone_status(intern_id)
                if status.get("completed", 0) == 0:
                    intern.recruiter_tag = RecruiterTag.RISK
                    self.db.commit()
                    return {"intern_id": intern_id, "risk_detected": True,
                            "reason": f"上手期已超时，进度严重滞后", "days_since_entry": days}

        return {"intern_id": intern_id, "risk_detected": False}
