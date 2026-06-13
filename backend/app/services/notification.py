"""
企微卡片合并推送服务
严格遵循 DEV_DOC 第10章推送策略：
- 全量合并原则：每 24 小时进行一次跨岗位数据清洗与大模型跑批
- 朝九单通道推送：每日 9:00 发送且仅发送一条合并摘要高级卡片
- 冷热隔离：正常新人折叠归纳，不发送独立卡片
"""
import os
import json
import httpx
from typing import List, Dict
from datetime import datetime


class WeComNotifier:
    """
    企业微信消息推送服务
    使用 Webhook Bot + 高级模板卡片实现冷热隔离合并推送
    """

    def __init__(self):
        self.webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")

    async def send_daily_mentor_card(self, mentor_name: str,
                                      mentor_id: int,
                                      normal_interns: List[Dict],
                                      warning_interns: List[Dict]) -> bool:
        """
        发送每日合并摘要卡片给导师
        冷热隔离：正常新人折叠，预警展开 + AI 小抄
        """
        if not self.webhook_url:
            print("[WeComNotifier] 未配置 WECOM_WEBHOOK_URL，跳过推送")
            return False

        # 构建模板卡片
        card = self._build_mentor_card(
            mentor_name, normal_interns, warning_interns
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.webhook_url,
                    json=card
                )
                if resp.status_code == 200:
                    print(f"[WeComNotifier] 已向导师 {mentor_name} 推送每日摘要")
                    return True
                else:
                    print(f"[WeComNotifier] 推送失败: {resp.status_code} {resp.text}")
                    return False
        except Exception as e:
            print(f"[WeComNotifier] 推送异常: {e}")
            return False

    def _build_mentor_card(self, mentor_name: str,
                            normal_interns: List[Dict],
                            warning_interns: List[Dict]) -> dict:
        """
        构建企微模板卡片
        完全对齐 DEV_DOC 第5.3.2节的卡片交互架构
        """
        normal_count = len(normal_interns)
        warning_count = len(warning_interns)
        total_count = normal_count + warning_count

        # 构建 Markdown 消息内容
        markdown_content = self._build_card_markdown(
            mentor_name, normal_interns, warning_interns,
            normal_count, warning_count, total_count
        )

        # 构建按钮
        buttons = self._build_card_buttons(warning_interns)

        return {
            "msgtype": "template_card",
            "template_card": {
                "card_type": "text_notice",
                "source": {
                    "icon_url": "",
                    "desc": "实习能量站",
                    "desc_color": 0
                },
                "main_title": {
                    "title": f"📢 实习能量站 · 带教今日摘要",
                    "desc": f"{datetime.now().strftime('%Y年%m月%d日')}"
                },
                "emphasis_content": {
                    "title": f"{total_count} 名实习生",
                    "desc": f"🟢 正常 {normal_count}人 | 🔴 预警 {warning_count}人"
                },
                "sub_title_text": markdown_content[:500],
                "horizontal_content_list": [
                    {
                        "keyname": "正常推进",
                        "value": f"{normal_count} 人"
                    },
                    {
                        "keyname": "需要关注",
                        "value": f"{warning_count} 人"
                    }
                ],
                "card_action": {
                    "type": 1,
                    "url": "https://your-domain.com/mentor"
                },
                "button_list": buttons
            }
        }

    def _build_card_markdown(self, mentor_name: str,
                              normal_interns: List[Dict],
                              warning_interns: List[Dict],
                              normal_count: int,
                              warning_count: int,
                              total_count: int) -> str:
        """构建卡片正文内容"""

        lines = [
            f"导师您好，您当前带教的 {total_count} 名实习生中：",
            ""
        ]

        # 正常区域（冷）
        if normal_count > 0:
            normal_names = "、".join(
                [i.get("name", "未知") for i in normal_interns[:3]]
            )
            if normal_count > 3:
                normal_names += f"等{normal_count}人"
            lines.append(f"🟢 正常（{normal_count}人）：{normal_names}")
            lines.append("状态稳步推进，无需打扰")
            lines.append("")

        # 预警区域（热）
        if warning_count > 0:
            lines.append(f"🔴 预警（{warning_count}人）：")
            for w in warning_interns[:3]:  # 最多展示3个预警
                name = w.get("name", "未知")
                reason = w.get("reason", "进度滞后")
                cheat_sheet = w.get("cheat_sheet", "")

                lines.append(f"")
                lines.append(f"⚠️ {name}：{reason}")
                if cheat_sheet:
                    lines.append(f"💡 AI 小抄：{cheat_sheet[:100]}")

        return "\n".join(lines)

    def _build_card_buttons(self, warning_interns: List[Dict]) -> list:
        """构建卡片交互按钮"""
        buttons = []

        if warning_interns:
            # 对每个预警实习生生成操作按钮
            for w in warning_interns[:2]:  # 最多 2 个预警的按钮
                name = w.get("name", "")
                intern_id = w.get("intern_id", 0)
                buttons.append({
                    "type": 1,
                    "text": f"👀 查看 {name} 详情",
                    "style": 1,
                    "key": f"view_intern_{intern_id}",
                    "url": f"https://your-domain.com/mentor?intern={intern_id}"
                })

        buttons.append({
            "type": 1,
            "text": "✅ 已知晓（消除所有警报）",
            "style": 2,
            "key": "acknowledge_all",
            "url": "https://your-domain.com/mentor/acknowledge-all"
        })

        return buttons

    async def send_simple_text(self, content: str) -> bool:
        """发送简单文本消息（用于测试）"""
        if not self.webhook_url:
            return False

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "text",
                        "text": {"content": content}
                    }
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def send_daily_hr_summary(self, report: Dict) -> bool:
        """
        发送 HR 每日摘要（简化版，HR 端主要通过 Web 看板查看）
        """
        if not self.webhook_url:
            return False

        markdown = f"""
## 📊 实习能量站 · HR 日报

**统计周期**：{report.get('period', '今日')}

- 在途实习生：{report.get('totalInterns', 0)} 人
- 平均进度：{report.get('avgProgress', 0)}%
- 绩优闪电：{report.get('lightningCount', 0)} 人
- 红灯风险：{report.get('riskCount', 0)} 人

[👉 查看完整看板](https://your-domain.com/hr)
"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.webhook_url,
                    json={
                        "msgtype": "markdown",
                        "markdown": {"content": markdown}
                    }
                )
                return resp.status_code == 200
        except Exception:
            return False


# ============================================================
# 每日定时推送调度器
# ============================================================

class DailyPushScheduler:
    """
    每日 9:00 定时推送调度
    使用 APScheduler 实现
    """

    def __init__(self):
        self.notifier = WeComNotifier()

    async def execute_daily_push(self, db_session):
        """
        执行每日合并推送
        流程：
        1. 遍历所有导师
        2. 按导师聚合实习生状态
        3. 冷热分离
        4. 发送合并卡片
        """
        from app.models.database import Intern, Mentor, MentorAlert, AlertStatus
        from app.services.state_machine import StateMachine
        from sqlalchemy import select

        sm = StateMachine(db_session)

        # 获取所有导师
        mentors = db_session.execute(select(Mentor)).scalars().all()

        results = []
        for mentor in mentors:
            # 获取名下实习生
            interns = db_session.execute(
                select(Intern).where(Intern.mentor_id == mentor.id)
            ).scalars().all()

            normal_list = []
            warning_list = []

            for intern in interns:
                state_info = sm.get_intern_state(intern.id)
                risk_info = sm.detect_risk(intern.id)

                if risk_info and risk_info.get("risk_detected"):
                    # 获取 AI 带教小抄
                    alert = db_session.execute(
                        select(MentorAlert).where(
                            MentorAlert.intern_id == intern.id,
                            MentorAlert.status == AlertStatus.ACTIVE
                        ).order_by(MentorAlert.created_at.desc())
                    ).scalars().first()

                    warning_list.append({
                        "intern_id": intern.id,
                        "name": intern.name,
                        "job_family": intern.job_family.value,
                        "current_state": intern.current_state.value,
                        "progress": state_info.get("progress_percent", 0),
                        "reason": risk_info.get("reason", ""),
                        "cheat_sheet": alert.cheat_sheet_text if alert else ""
                    })
                else:
                    normal_list.append({
                        "intern_id": intern.id,
                        "name": intern.name,
                        "job_family": intern.job_family.value,
                        "current_state": intern.current_state.value,
                        "progress": state_info.get("progress_percent", 0)
                    })

            if normal_list or warning_list:
                success = await self.notifier.send_daily_mentor_card(
                    mentor.name, mentor.id, normal_list, warning_list
                )
                results.append({
                    "mentor_id": mentor.id,
                    "mentor_name": mentor.name,
                    "normal_count": len(normal_list),
                    "warning_count": len(warning_list),
                    "sent": success
                })

        return results


# 全局单例
wecom_notifier = WeComNotifier()
daily_scheduler = DailyPushScheduler()
