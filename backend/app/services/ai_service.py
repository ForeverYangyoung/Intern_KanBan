"""
AI 服务层 — 腾讯混元大模型专区 v3.0

核心原则变更：
1. AI 定位从"决策者"降级为"提炼者"：只提取/结构化数据，不产生任何决策判断
2. 严禁 AI 输出 risk_assessment、overall_assessment、是否需要介入 等决策性字段
3. AI 输出格式强制为 Strict JSON，仅包含结构化事实提取
4. 所有"裁判权"（风险评估、风控打标、是否需要通知导师）由纯数据规则引擎执行

双轨调度（保留）：
- hunyuan-standard：白天轨 Copilot 数据提炼
- hunyuan-pro：深夜轨深度数据挖掘（仅提炼，不决策）
"""
import json
import os
import httpx
from typing import List, Dict, Any, Optional


class HunyuanAIService:
    """
    腾讯混元大模型服务 — 降级为纯数据提炼工具
    严禁输出任何决策性结论："建议...""应该...""判定为...""需要介入..."
    """

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("HUNYUAN_API_KEY", "")
        self.base_url = base_url or os.getenv("HUNYUAN_BASE_URL",
                                              "https://hunyuan.tencentcloudapi.com")
        self.model_pro = os.getenv("HUNYUAN_MODEL_PRO", "hunyuan-pro")
        self.model_standard = os.getenv("HUNYUAN_MODEL_STANDARD", "hunyuan-standard")

    async def _call_hunyuan(self, system_prompt: str, user_prompt: str,
                            model: str = None, temperature: float = 0.2) -> str:
        """通用混元调用"""
        model = model or self.model_standard
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature,
                        "response_format": {"type": "json_object"}
                    }
                )
                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                print(f"[HunyuanAI] 调用失败: {data}")
                return "{}"
        except Exception as e:
            print(f"[HunyuanAI] LLM 调用异常: {e}")
            return "{}"

    # ============================================================
    # 场景1：CR 事实提取（仅提炼数据特征，不判断）
    # ============================================================
    async def extract_cr_facts(self, raw_cr_log: list) -> dict:
        """从 CR 日志中提取纯技术事实，不含任何判断"""
        if not raw_cr_log:
            return {"common_topics": [], "architecture_mentions": [], "data_sources": 0}

        cr_text = json.dumps(raw_cr_log, ensure_ascii=False)
        system_prompt = """你是代码审查数据提取工具。
你的唯一任务：从 CR 评论中提取客观事实。
严禁输出任何判断、建议、评估。只输出 JSON 格式的事实数据。
不要输出 "建议...""需要...""判定..." 等任何决策性内容。"""

        user_prompt = f"""CR评论原始数据：
{cr_text}

请严格按以下JSON格式返回客观事实（不要添加判断）：
{{
  "common_topics": ["被提及≥3次的技术主题列表"],
  "architecture_mentions": ["包含"架构""设计""扩展性"等词汇的评论摘要"],
  "code_standards_mentions": ["编码规范相关评论数量与类型"],
  "data_source_count": 评论总数
}}

核心要求：
- common_topics: 只列出被3位及以上reviewer提及的技术主题，格式如 "Redis分布式锁"
- architecture_mentions: 只摘录包含架构相关关键词的原始句子片段
- 不要输出 "质量评价""风险判断""改进建议" 等任何决策性字段
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_pro)
        try:
            parsed = json.loads(result)
            return {
                "common_topics": parsed.get("common_topics", []),
                "architecture_mentions": parsed.get("architecture_mentions", []),
                "code_standards_mentions": parsed.get("code_standards_mentions", []),
                "data_source_count": parsed.get("data_source_count", 0),
            }
        except json.JSONDecodeError:
            return {"common_topics": [], "architecture_mentions": [], "code_standards_mentions": [], "data_source_count": 0}

    # ============================================================
    # 场景2：一致性校验（对比数据，不上报"欺骗"）
    # ============================================================
    async def compare_report_with_logs(self, reported_text: str,
                                        actual_behavior_log: dict) -> dict:
        """对比实习生汇报与系统日志，输出差异点（非判断）"""
        if not reported_text:
            return {"differences": [], "match_ratio": 0.0}

        system_prompt = """你是数据对齐工具。
你的唯一任务：对比两份数据描述，列出它们之间的差异项。
严禁输出 "欺骗""虚报""夸大" 等定性词语。只描述事实差异。
例如：可以说"日报提到完成了3个commit，系统日志显示2个commit"，不能说"实习生存在夸大行为"。"""

        user_prompt = f"""
实习生汇报内容：
{reported_text}

系统日志摘要：
{json.dumps(actual_behavior_log, ensure_ascii=False)}

请对比差异，严格按以下JSON格式返回：
{{
  "differences": [
    "差异描述1（纯事实，不带判断，如：汇报提到合并了PR-123，日志显示最新PR为PR-120）"
  ],
  "matching_items": ["描述一致的条目"],
  "match_ratio": 0.0-1.0
}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_standard)
        try:
            parsed = json.loads(result)
            return {
                "differences": parsed.get("differences", []),
                "matching_items": parsed.get("matching_items", []),
                "match_ratio": parsed.get("match_ratio", 0.0),
            }
        except json.JSONDecodeError:
            return {"differences": [], "matching_items": [], "match_ratio": 0.0}

    # ============================================================
    # 场景3：带教证据提炼（导师手写 → 组织建设素材，仅润色）
    # ============================================================
    async def polish_mentor_evidence(self, mentor_name: str, intern_name: str,
                                      raw_evidence: str, alert_level: str) -> str:
        """将导师口语化带教内容润色为组织建设贡献描述（仅润色，不添加内容）"""
        system_prompt = """你是组织建设记录写作助手。
你的唯一任务：将导师的口语化带教记录润色为简洁的组织建设贡献描述。
要求：
1. 仅润色语言风格，不添加原文中不存在的事实
2. 保留导师原话的核心内容
3. 不要添加 "建议给予绩效加分" 等评价性语句
4. 输出纯文本，不超过150字"""

        user_prompt = f"""
导师 {mentor_name} 对实习生 {intern_name} 的带教记录（预警等级: {alert_level}）：
{raw_evidence}

请润色为组织建设贡献描述：
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_standard)
        return result[:300]

    # ============================================================
    # 场景4：PRD 评论区语义聚类（仅分类，不判断）
    # ============================================================
    async def cluster_prd_comments(self, review_comments: list) -> dict:
        """对 PRD 评论进行语义聚类，仅输出分类，不做质量判断"""
        system_prompt = """你是文本分类工具。
你的唯一任务：将PRD评审评论按主题进行聚类。
严禁输出 "PRD质量差""需要重写" 等判断性内容。
只输出每个聚类包含的评论数量和代表性摘录。"""

        user_prompt = f"""
PRD评审评论：
{json.dumps(review_comments, ensure_ascii=False)}

请严格按以下JSON格式返回（仅事实分类）：
{{
  "clusters": [
    {{"theme": "技术可行性", "count": 0, "sample": "代表性评论摘录"}},
    {{"theme": "业务边界", "count": 0, "sample": "代表性评论摘录"}},
    {{"theme": "用户体验", "count": 0, "sample": "代表性评论摘录"}},
    {{"theme": "其他", "count": 0, "sample": ""}}
  ],
  "total_comments": 0,
  "latest_comment_time": "最近评论时间"
}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_pro)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"clusters": [], "total_comments": 0}

    # ============================================================
    # 场景5：销售跟进摘要（仅提取特征，不判断质量）
    # ============================================================
    async def extract_sales_patterns(self, followup_summaries: list) -> dict:
        """从销售跟进记录中提取模式特征"""
        system_prompt = """你是CRM数据分析工具。
你的唯一任务：从销售跟进记录中提取统计特征。
严禁输出 "跟进质量差""话术生硬" 等判断。只输出客观数据。"""

        user_prompt = f"""
销售跟进记录：
{json.dumps(followup_summaries, ensure_ascii=False)}

请严格按以下JSON格式返回：
{{
  "total_records": 0,
  "average_length_chars": 0,
  "common_phrases": ["出现≥3次的话术模板短语"],
  "has_customer_feedback": ["包含客户反馈的记录摘要列表"],
  "time_distribution": "按时间分布描述"
}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_standard)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"total_records": 0, "average_length_chars": 0}

    # ============================================================
    # 场景6：Copilot 弹窗事实提炼（仅提炼上下文，不给出建议）
    # ============================================================
    async def extract_copilot_context(self, intern_name: str,
                                       breakdown_type: str,
                                       recent_data: dict) -> dict:
        """为 Copilot 弹窗提炼上下文事实，不直接给建议"""
        system_prompt = """你是技术上下文提炼工具。
你的唯一任务：从实习生崩溃数据中提炼关键上下文信息。
严禁输出 "建议实习生...""导师应该..." 等建议性内容。
只输出：发现了什么问题 + 相关的数据背景。
格式：{"situation": "当前状况", "data_points": ["相关数据点1", "数据点2"], "related_docs": ["可能相关的文档关键词"]}"""

        user_prompt = f"""
实习生 {intern_name} 遇到了崩溃卡点：{breakdown_type}

近期数据：
{json.dumps(recent_data, ensure_ascii=False)}

请提炼关键上下文：
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_standard)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"situation": "系统检测到异常", "data_points": [], "related_docs": []}

    # ============================================================
    # 场景7：成长错题本归纳（仅聚类卡点模式，不判断）
    # ============================================================
    async def cluster_error_patterns(self, error_events: list) -> dict:
        """归纳重复卡点模式"""
        system_prompt = """你是模式识别工具。
你的唯一任务：从一系列历史卡点事件中找出重复出现的模式。
仅输出模式名称和出现次数，不输出任何建议。"""

        user_prompt = f"""
历史卡点事件：
{json.dumps(error_events, ensure_ascii=False)}

请严格按JSON格式返回：
{{
  "patterns": [
    {{"pattern": "REDIS_BOUNDARY_DEADLOCK", "count": 3, "related_events": ["event1", "event2"]}}
  ]
}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt, model=self.model_standard)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"patterns": []}

    # ============================================================
    # 保留：智能推荐（非决策，只是匹配）
    # ============================================================
    async def get_daily_recommendations(self, tasks: list,
                                         custom_tasks: list) -> list:
        """根据任务主题匹配学习资源（纯匹配，非决策）"""
        all_tasks = (tasks or []) + (custom_tasks or [])
        if not all_tasks:
            return []

        system_prompt = """你是知识库匹配工具。根据任务关键词匹配相关学习资源。只输出JSON，不做任何建议。"""
        user_prompt = f"""
任务列表：
{json.dumps(all_tasks, ensure_ascii=False)}

请推荐 3 个学习资源，JSON 格式：
[{{"type": "case|doc|video", "tag": "标签", "title": "资源标题", "desc": "关联说明"}}]
"""

        result = await self._call_hunyuan(system_prompt, user_prompt)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []

    async def generate_weekly_insight(self, all_interns: list) -> list:
        """HR 周报数据洞察（仅数据观察，不决策）"""
        system_prompt = """你是HR数据观察工具。从数据中发现值得关注的变化趋势。仅描述数据表现，不做决策性建议。"""
        user_prompt = f"""
本周实习生数据：
{json.dumps(all_interns, ensure_ascii=False)}

请给出 3 条数据观察，JSON 格式：
{{"insights": ["数据观察1（纯事实描述）", "数据观察2", "数据观察3"]}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt)
        try:
            parsed = json.loads(result)
            return parsed.get("insights", [])
        except json.JSONDecodeError:
            return []


# 全局单例
hunyuan_service = HunyuanAIService()
