"""
里程碑状态机引擎 — 核心资产
实现事件驱动的状态流转：ONBOARDING → RAMP_UP → INDEPENDENT
"""
import json
from datetime import date
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.database import (
    Intern, MilestoneConfig, RDSnapshot, SalesSnapshot,
    StateNode, JobFamily, RecruiterTag, MentorAlert,
    AlertLevel, AlertStatus
)


class StateMachine:
    """
    岗位标准里程碑状态机
    摒弃时间推进制，改为事件触发制
    """

    def __init__(self, db: Session):
        self.db = db

    def process_rd_event(self, intern_id: int, event_type: str,
                          event_data: Optional[Dict] = None) -> Dict:
        """
        处理研发线事件
        event_type: DEV_ENV_SETUP_DONE / CODE_STANDARD_PASSED /
                    FIRST_BUG_RESOLVED / FIRST_PR_MERGED /
                    MODULE_OWNERSHIP_ASSIGNED / DELIVERY_ON_TIME_3_WEEKS
        """
        return self._process_event(intern_id, event_type, JobFamily.RD, event_data)

    def process_pm_event(self, intern_id: int, event_type: str,
                          event_data: Optional[Dict] = None) -> Dict:
        """处理产品线事件"""
        return self._process_event(intern_id, event_type, JobFamily.PM, event_data)

    def process_sales_event(self, intern_id: int, event_type: str,
                             event_data: Optional[Dict] = None) -> Dict:
        """处理销售线事件"""
        return self._process_event(intern_id, event_type, JobFamily.SALES, event_data)

    def _process_event(self, intern_id: int, event_type: str,
                       job_family: JobFamily,
                       event_data: Optional[Dict] = None) -> Dict:
        """
        核心状态机判定逻辑
        1. 查找当前状态
        2. 查找当前阶段所需的所有里程碑
        3. 判断是否满足通关条件 → 状态流转
        """
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return {"success": False, "message": f"实习生 ID {intern_id} 不存在"}

        current_state = intern.current_state
        old_state = current_state

        # 查找当前阶段的所有里程碑配置
        milestones = self.db.execute(
            select(MilestoneConfig).where(
                MilestoneConfig.job_family == job_family,
                MilestoneConfig.state_node == current_state
            )
        ).scalars().all()

        if not milestones:
            return {
                "success": True,
                "state_changed": False,
                "message": f"当前阶段 {current_state.value} 无里程碑配置",
                "current_state": current_state.value
            }

        # 统计当前阶段事件完成情况
        completed_count = self._count_completed_events(intern_id, job_family, current_state)

        # 记录本次事件
        self._log_event(intern_id, event_type, event_data)

        # 重新统计
        completed_count = self._count_completed_events(intern_id, job_family, current_state)
        required_count = len(milestones)

        result = {
            "success": True,
            "state_changed": False,
            "current_state": current_state.value,
            "event": event_type,
            "completed_milestones": completed_count,
            "total_milestones": required_count,
            "progress_percent": round(completed_count / max(required_count, 1) * 100, 1)
        }

        # 判定是否满足通关条件
        if completed_count >= required_count:
            next_state = self._get_next_state(current_state)
            if next_state:
                intern.current_state = next_state
                self.db.commit()
                result["state_changed"] = True
                result["old_state"] = old_state.value
                result["current_state"] = next_state.value
                result["message"] = f"🎉 通关！从 {old_state.value} 晋升至 {next_state.value}"

                # 检查是否需要更新风控标签（绩优闪电检测）
                self._check_lightning_promotion(intern)
            else:
                result["message"] = f"已完成 {current_state.value} 全部里程碑，已是最终阶段"
        else:
            result["message"] = (
                f"里程碑进度: {completed_count}/{required_count}，"
                f"尚不满足通关条件"
            )

        return result

    def _get_next_state(self, current: StateNode) -> Optional[StateNode]:
        """获取下一个状态"""
        state_order = [StateNode.ONBOARDING, StateNode.RAMP_UP, StateNode.INDEPENDENT]
        try:
            idx = state_order.index(current)
            if idx + 1 < len(state_order):
                return state_order[idx + 1]
        except ValueError:
            pass
        return None

    def _count_completed_events(self, intern_id: int,
                                 job_family: JobFamily,
                                 state_node: StateNode) -> int:
        """
        根据岗位类型和当前状态，统计已完成的事件数
        这里统计对应快照表中满足条件的数据条数
        """
        if job_family == JobFamily.RD:
            # 查询研发快照表
            if state_node == StateNode.ONBOARDING:
                # 融入期：有commit记录 = DEV_ENV_SETUP_DONE
                snapshots = self.db.execute(
                    select(RDSnapshot).where(
                        RDSnapshot.intern_id == intern_id
                    )
                ).scalars().all()
                count = 0
                for s in snapshots:
                    if s.commit_count > 0:
                        count += 1  # 环境配置完成
                    if s.cr_total_comments > 0:
                        count += 1  # 代码规范考核（简化：有CR评论即视为考核通过）
                return min(count, 2)  # 融入期最多2个里程碑

            elif state_node == StateNode.RAMP_UP:
                snapshots = self.db.execute(
                    select(RDSnapshot).where(
                        RDSnapshot.intern_id == intern_id
                    )
                ).scalars().all()
                count = 0
                for s in snapshots:
                    if s.bug_resolved_count > 0:
                        count += 1
                    if s.pr_merged_count > 0:
                        count += 1
                return min(count, 2)

            elif state_node == StateNode.INDEPENDENT:
                snapshots = self.db.execute(
                    select(RDSnapshot).where(
                        RDSnapshot.intern_id == intern_id
                    )
                ).scalars().all()
                count = 0
                for s in snapshots:
                    if s.pr_merged_count >= 3:
                        count += 1  # 独立Owner
                    if s.bug_resolved_count >= 5:
                        count += 1  # 交付准时率
                return min(count, 2)

        elif job_family == JobFamily.SALES:
            snapshots = self.db.execute(
                select(SalesSnapshot).where(
                    SalesSnapshot.intern_id == intern_id
                )
            ).scalars().all()

            if state_node == StateNode.ONBOARDING:
                count = 0
                for s in snapshots:
                    if s.effective_call_duration > 0:
                        count += 1  # 话术通关
                    if s.crm_leads_touched > 0:
                        count += 1  # CRM熟悉
                return min(count, 2)

            elif state_node == StateNode.RAMP_UP:
                count = 0
                for s in snapshots:
                    if s.crm_leads_touched >= 3:
                        count += 1
                return min(count, 1)

            elif state_node == StateNode.INDEPENDENT:
                count = 0
                for s in snapshots:
                    if s.crm_leads_touched >= 10:
                        count += 1
                return min(count, 1)

        # PM 线暂用简化逻辑
        return 0

    def _log_event(self, intern_id: int, event_type: str,
                   event_data: Optional[Dict] = None):
        """记录事件到对应快照表（在 process_rd_event 之前已由 webhook 写入）"""
        # 快照写入由 webhook 路由负责，这里只做事件审计
        pass

    def _check_lightning_promotion(self, intern: Intern):
        """
        绩优闪电检测：
        连续两周状态机通关速度处于同岗位前 10%
        简化版：从 ONBOARDING → RAMP_UP 的通关时长判断
        """
        # 查询同岗位所有实习生的平均通关时长
        # 简化版：如果 intern 当前是 INDEPENDENT，直接打标 LIGHTNING
        if intern.current_state == StateNode.INDEPENDENT:
            intern.recruiter_tag = RecruiterTag.LIGHTNING
            self.db.commit()

    def get_intern_state(self, intern_id: int) -> Dict:
        """查询实习生当前状态机信息"""
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return {"success": False, "message": "实习生不存在"}

        milestones = self.db.execute(
            select(MilestoneConfig).where(
                MilestoneConfig.job_family == intern.job_family,
                MilestoneConfig.state_node == intern.current_state
            )
        ).scalars().all()

        completed = self._count_completed_events(
            intern_id, intern.job_family, intern.current_state
        )

        return {
            "intern_id": intern_id,
            "name": intern.name,
            "job_family": intern.job_family.value,
            "current_state": intern.current_state.value,
            "recruiter_tag": intern.recruiter_tag.value,
            "current_milestones": [
                {
                    "name": m.milestone_name,
                    "trigger_event": m.trigger_event,
                    "required_count": m.required_count
                }
                for m in milestones
            ],
            "completed_count": completed,
            "total_count": len(milestones),
            "progress_percent": round(completed / max(len(milestones), 1) * 100, 1)
        }

    def create_alert(self, mentor_id: int, intern_id: int,
                     alert_level: AlertLevel, cheat_sheet_text: str) -> MentorAlert:
        """创建导师预警记录"""
        alert = MentorAlert(
            mentor_id=mentor_id,
            intern_id=intern_id,
            alert_level=alert_level,
            cheat_sheet_text=cheat_sheet_text,
            status=AlertStatus.ACTIVE
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def get_active_alerts(self, mentor_id: int) -> list:
        """获取导师名下所有活跃预警"""
        alerts = self.db.execute(
            select(MentorAlert).where(
                MentorAlert.mentor_id == mentor_id,
                MentorAlert.status == AlertStatus.ACTIVE
            )
        ).scalars().all()

        result = []
        for alert in alerts:
            intern = self.db.get(Intern, alert.intern_id)
            result.append({
                "id": alert.id,
                "intern_id": alert.intern_id,
                "intern_name": intern.name if intern else "未知",
                "alert_level": alert.alert_level.value,
                "cheat_sheet_text": alert.cheat_sheet_text,
                "status": alert.status.value,
                "created_at": alert.created_at.isoformat() if alert.created_at else None
            })
        return result

    def resolve_alert(self, alert_id: int) -> bool:
        """消除预警"""
        alert = self.db.get(MentorAlert, alert_id)
        if alert:
            alert.status = AlertStatus.RESOLVED
            from datetime import datetime
            alert.resolved_at = datetime.now()
            self.db.commit()
            return True
        return False

    def detect_risk(self, intern_id: int) -> Optional[Dict]:
        """
        红灯风险检测：
        连续两周触发状态机卡点，或同一技术盲点被驳回 3 次以上
        """
        intern = self.db.get(Intern, intern_id)
        if not intern:
            return None

        # 简化版：检查当前阶段停留时间
        # 如果融入期超过 14 天未通关，标记为风险
        from datetime import datetime, timedelta
        if intern.current_state == StateNode.ONBOARDING:
            if intern.entry_date:
                days_since_entry = (date.today() - intern.entry_date).days
                if days_since_entry > 14:
                    # 检查是否完成任何里程碑
                    completed = self._count_completed_events(
                        intern_id, intern.job_family, intern.current_state
                    )
                    if completed == 0:
                        intern.recruiter_tag = RecruiterTag.RISK
                        self.db.commit()
                        return {
                            "intern_id": intern_id,
                            "risk_detected": True,
                            "reason": f"入职 {days_since_entry} 天仍未完成任何融入期里程碑",
                            "days_since_entry": days_since_entry
                        }

        # RAMP_UP 阶段超过 21 天未通关
        if intern.current_state == StateNode.RAMP_UP:
            if intern.entry_date:
                days_since_entry = (date.today() - intern.entry_date).days
                if days_since_entry > 35:  # 2周融入 + 3周上手 = 35天
                    completed = self._count_completed_events(
                        intern_id, intern.job_family, intern.current_state
                    )
                    if completed == 0:
                        intern.recruiter_tag = RecruiterTag.RISK
                        self.db.commit()
                        return {
                            "intern_id": intern_id,
                            "risk_detected": True,
                            "reason": f"上手期已超过预期时长，进度严重滞后",
                            "days_since_entry": days_since_entry
                        }

        return {"intern_id": intern_id, "risk_detected": False}
