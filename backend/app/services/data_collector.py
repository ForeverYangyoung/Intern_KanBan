"""
数据采集服务 — 多源异构数据采集层
严格按照 DEV_DOC 第9章合规铁律：
- 严禁采集群聊文字等隐私数据
- 仅抓取具有明确智力交付属性的影子日志
- 实施脏数据清洗规则

对接源：
  研发线：腾讯工蜂 + TAPD
  产品线：腾讯文档 + TAPD
  销售线：企微 CRM + 会议 ASR
"""
import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import httpx


class DataCollector:
    """
    多源数据采集器
    通过 Webhook 回调 + OpenAPI 实现影子采集
    """

    def __init__(self):
        # 各平台 API 配置
        self.gongfeng_api = os.getenv("GONGFENG_API_URL", "")
        self.gongfeng_token = os.getenv("GONGFENG_API_TOKEN", "")
        self.tapd_api = os.getenv("TAPD_API_URL", "")
        self.tapd_token = os.getenv("TAPD_API_TOKEN", "")
        self.wecom_crm_api = os.getenv("WECOM_CRM_API_URL", "")
        self.wecom_crm_token = os.getenv("WECOM_CRM_TOKEN", "")

    async def collect_all(self, intern_id: int, days: int = 7) -> List[Dict]:
        """采集指定实习生近 N 天的所有数据源"""
        all_snapshots = []
        since_date = datetime.now() - timedelta(days=days)

        collectors = [
            ("gongfeng", self._collect_gongfeng_data),
            ("tapd", self._collect_tapd_data),
            ("wecom_crm", self._collect_wecom_crm_data),
            ("doc", self._collect_doc_data),
        ]

        for source_name, collector in collectors:
            try:
                snapshots = await collector(intern_id, since_date)
                all_snapshots.extend(snapshots)
            except Exception as e:
                print(f"[DataCollector] {source_name} 采集失败: {e}")

        # 应用脏数据清洗规则
        all_snapshots = self._clean_dirty_data(all_snapshots)

        return all_snapshots

    async def _collect_gongfeng_data(self, intern_id: int,
                                      since: datetime) -> List[Dict]:
        """
        采集腾讯工蜂数据
        指标: 提交次数、代码行数、PR 合入数、CR 评论数

        对接方式:
        - 主动拉取: GET /api/v4/users/{user_id}/events
        - 被动接收: POST /api/webhook/gongfeng/pr
        """
        if not self.gongfeng_api:
            return self._mock_gongfeng_data()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.gongfeng_api}/users/{intern_id}/events",
                    headers={"PRIVATE-TOKEN": self.gongfeng_token},
                    params={"after": since.isoformat()}
                )
                if resp.status_code == 200:
                    events = resp.json()
                    return self._parse_gongfeng_events(events)
        except Exception:
            pass

        return self._mock_gongfeng_data()

    def _parse_gongfeng_events(self, events: list) -> List[Dict]:
        """解析工蜂事件为统一快照格式"""
        today = datetime.now().isoformat()
        commits = sum(1 for e in events if e.get("action_name") == "pushed to")
        pr_merged = sum(1 for e in events if e.get("action_name") == "accepted")
        cr_comments = sum(1 for e in events if e.get("action_name") == "commented on")

        return [{
            "source": "gongfeng",
            "snapshot_date": today,
            "metrics": {
                "commits": commits,
                "pr_merged": pr_merged,
                "cr_comments": cr_comments
            },
            "raw_events": events[:50]  # 保留最近 50 条事件
        }]

    async def _collect_tapd_data(self, intern_id: int,
                                  since: datetime) -> List[Dict]:
        """
        采集 TAPD 数据
        指标: 完成任务数、Bug修复数、需求参与数
        """
        if not self.tapd_api:
            return self._mock_tapd_data()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.tapd_api}/tasks",
                    headers={"Authorization": f"Bearer {self.tapd_token}"},
                    params={"owner": str(intern_id), "modified": f">{since.strftime('%Y-%m-%d')}"}
                )
                if resp.status_code == 200:
                    tasks = resp.json()
                    return self._parse_tapd_tasks(tasks)
        except Exception:
            pass

        return self._mock_tapd_data()

    def _parse_tapd_tasks(self, tasks: list) -> List[Dict]:
        """解析 TAPD 任务"""
        today = datetime.now().isoformat()
        completed = sum(1 for t in tasks if t.get("status") == "done" or t.get("status") == "closed")
        bugs = sum(1 for t in tasks if t.get("type") == "bug")
        stories = sum(1 for t in tasks if t.get("type") == "story")

        return [{
            "source": "tapd",
            "snapshot_date": today,
            "metrics": {
                "tasks_completed": completed,
                "bugs_fixed": bugs,
                "stories_involved": stories
            },
            "raw_tasks": tasks[:50]
        }]

    async def _collect_wecom_crm_data(self, intern_id: int,
                                       since: datetime) -> List[Dict]:
        """
        采集企微 CRM 数据
        指标: 触达线索数、有效通话时长、跟进小结

        合规边界：仅采集 CRM 系统记录的商务行为数据，
        严禁采集群聊/私聊文字记录
        """
        if not self.wecom_crm_api:
            return self._mock_wecom_crm_data()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.wecom_crm_api}/activities",
                    headers={"Authorization": f"Bearer {self.wecom_crm_token}"},
                    params={"user_id": str(intern_id), "since": since.isoformat()}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_wecom_crm_data(data)
        except Exception:
            pass

        return self._mock_wecom_crm_data()

    def _parse_wecom_crm_data(self, data: dict) -> List[Dict]:
        """解析企微 CRM 数据"""
        today = datetime.now().isoformat()
        return [{
            "source": "wecom_crm",
            "snapshot_date": today,
            "metrics": {
                "leads_touched": data.get("leads_count", 0),
                "call_duration": data.get("total_call_seconds", 0),
                "followup_summaries": data.get("summaries", [])
            }
        }]

    async def _collect_doc_data(self, intern_id: int,
                                 since: datetime) -> List[Dict]:
        """
        采集腾讯文档数据
        指标: 文档阅读时长、产出文档数
        脏数据清洗: 时长 > 4h 且无键盘/鼠标交互 → 标记为挂机噪音
        """
        # 腾讯文档 API 对接（待实现）
        return self._mock_doc_data()

    # ============================================================
    # 脏数据清洗规则
    # ============================================================

    def _clean_dirty_data(self, snapshots: List[Dict]) -> List[Dict]:
        """
        应用 DEV_DOC 第9章脏数据清洗规则：
        1. 代码防刷：剔除 500 行以上的第三方开源库直接拷贝
        2. 时长防挂：文档停留时长 > 4h 且无交互 → 标记为挂机噪音
        """
        cleaned = []
        for snapshot in snapshots:
            if snapshot["source"] == "gongfeng":
                # 过滤超大代码提交（疑似第三方库拷贝）
                metrics = snapshot.get("metrics", {})
                if metrics.get("lines_added", 0) > 500:
                    print(f"[DataCleaner] 疑似第三方库拷贝，已过滤超大提交")
                    continue

            if snapshot["source"] == "doc":
                metrics = snapshot.get("metrics", {})
                reading_minutes = metrics.get("reading_minutes", 0)
                has_interaction = metrics.get("has_interaction", True)
                if reading_minutes > 240 and not has_interaction:
                    print(f"[DataCleaner] 疑似挂机刷时长（>4h无交互），已标记为噪音")
                    metrics["is_noise"] = True
                    metrics["reading_minutes"] = 0

            cleaned.append(snapshot)
        return cleaned

    # ============================================================
    # 模拟数据（MVP 阶段降级方案）
    # ============================================================

    def _mock_gongfeng_data(self) -> List[Dict]:
        return [{
            "source": "gongfeng",
            "snapshot_date": datetime.now().isoformat(),
            "metrics": {
                "commits": 5,
                "pr_merged": 1,
                "cr_comments": 3,
                "lines_added": 200,
                "lines_deleted": 50
            }
        }]

    def _mock_tapd_data(self) -> List[Dict]:
        return [{
            "source": "tapd",
            "snapshot_date": datetime.now().isoformat(),
            "metrics": {
                "tasks_completed": 2,
                "bugs_fixed": 1,
                "stories_involved": 3
            }
        }]

    def _mock_wecom_crm_data(self) -> List[Dict]:
        return [{
            "source": "wecom_crm",
            "snapshot_date": datetime.now().isoformat(),
            "metrics": {
                "leads_touched": 5,
                "call_duration": 1800,
                "followup_summaries": []
            }
        }]

    def _mock_doc_data(self) -> List[Dict]:
        return [{
            "source": "doc",
            "snapshot_date": datetime.now().isoformat(),
            "metrics": {
                "reading_minutes": 90,
                "docs_created": 1,
                "wiki_edits": 2,
                "has_interaction": True
            }
        }]

    # ============================================================
    # 进度分数计算
    # ============================================================

    def calculate_progress_score(self, snapshots: List[Dict]) -> int:
        """
        根据采集数据计算进度分数（0-100）
        各数据源加权综合
        """
        weights = {"gongfeng": 0.35, "tapd": 0.30, "doc": 0.20, "wecom_crm": 0.15}
        score = 0
        valid_count = 0

        for snapshot in snapshots:
            source = snapshot.get("source", "")
            if source not in weights:
                continue

            metrics = snapshot.get("metrics", {})
            source_score = self._normalize_metrics(source, metrics)
            score += source_score * weights[source]
            valid_count += 1

        if valid_count == 0:
            return 0
        return min(int(score * 100 / sum(weights[s["source"]] for s in snapshots
                                          if s["source"] in weights)), 100)

    def _normalize_metrics(self, source: str, metrics: Dict) -> float:
        """将各数据源指标归一化到 0-1"""
        thresholds = {
            "gongfeng": {"commits": 10, "pr_merged": 3, "cr_comments": 5},
            "tapd": {"tasks_completed": 5, "bugs_fixed": 3},
            "wecom_crm": {"leads_touched": 10, "call_duration": 3600},
            "doc": {"reading_minutes": 180, "docs_created": 3}
        }

        th = thresholds.get(source, {})
        if not th:
            return 0.5

        total = 0
        count = 0
        for key, threshold in th.items():
            value = metrics.get(key, 0)
            total += min(value / max(threshold, 1), 1.0)
            count += 1

        return total / max(count, 1)


# 全局单例
data_collector = DataCollector()
