"""
AI 服务层 — 腾讯混元大模型专区
严格按照 DEV_DOC 第8章设计：
- hunyuan-pro：复杂深度校验（CR 审计）
- hunyuan-standard：高性价比事实提取（一致性校验）

所有 AI 计算集中在后台静默批处理层
输出强制使用 Strict JSON Schema
"""
import json
import os
import httpx
from typing import List, Dict, Any, Optional


class HunyuanAIService:
    """
    腾讯混元大模型服务封装
    全面转向 Strict JSON Schema 结构化事实提取
    """

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.getenv("HUNYUAN_API_KEY", "")
        self.base_url = base_url or os.getenv("HUNYUAN_BASE_URL",
                                              "https://hunyuan.tencentcloudapi.com")
        self.model_pro = os.getenv("HUNYUAN_MODEL_PRO", "hunyuan-pro")
        self.model_standard = os.getenv("HUNYUAN_MODEL_STANDARD", "hunyuan-standard")

    async def _call_hunyuan(self, system_prompt: str, user_prompt: str,
                            model: str = None, temperature: float = 0.3) -> str:
        """
        通用混元大模型调用
        兼容 OpenAI 格式（混元支持该接口格式）
        """
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
                else:
                    print(f"[HunyuanAI] 调用失败: {data}")
                    return "{}"
        except Exception as e:
            print(f"[HunyuanAI] LLM 调用异常: {e}")
            return "{}"

    # ============================================================
    # 场景一：非结构化 CR 评语审计（研发岗）— hunyuan-pro
    # ============================================================

    async def audit_gongfeng_cr(self, raw_cr_log: list) -> dict:
        """
        输入：工蜂平台上导师对实习生的 CR 原始评语文本
        模型：hunyuan-pro（长文本处理与代码逻辑理解能力强）
        输出：结构化技术事实

        Prompt 逻辑：扮演"腾讯开源委员会技术审计专家"
        严格提取两项指标，禁止主观添加：
        1. 实习生是否在同一知识点重复犯错超过 3 次
        2. 导师是否提及架构性缺陷
        """
        if not raw_cr_log:
            return {
                "has_repeated_mistakes": False,
                "repeated_topic": "",
                "repeat_count": 0,
                "has_architecture_issue": False,
                "architecture_detail": "",
                "overall_assessment": "暂无 CR 数据"
            }

        cr_text = json.dumps(raw_cr_log, ensure_ascii=False)

        system_prompt = """你是一位腾讯开源委员会技术审计专家。
你的任务是从工蜂 Code Review 评语中提取结构化技术事实。
严格遵循以下规则：
1. 只提取明确可验证的事实，禁止任何主观推断
2. 如果同一知识点被指出问题超过 3 次，标记为 repeated_mistakes
3. 识别导师是否明确提到"架构"、"设计模式"、"扩展性"等架构性词汇
4. 输出必须是严格的 JSON 格式"""

        user_prompt = f"""
以下是实习生在工蜂平台上的 Code Review 原始评语：

{cr_text}

请提取以下信息，以 JSON 格式返回：
{{
  "has_repeated_mistakes": true/false,
  "repeated_topic": "重复出错的知知识点（如 Redis分布式锁、空指针处理等）",
  "repeat_count": 0,
  "has_architecture_issue": true/false,
  "architecture_detail": "导师提到的架构性缺陷描述",
  "overall_assessment": "50字以内的整体技术评价"
}}
"""

        result = await self._call_hunyuan(
            system_prompt, user_prompt, model=self.model_pro
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "has_repeated_mistakes": False,
                "repeated_topic": "",
                "repeat_count": 0,
                "has_architecture_issue": False,
                "architecture_detail": "",
                "overall_assessment": "CR 审计解析失败"
            }

    # ============================================================
    # 场景二：双向一致性反作弊侦探 — hunyuan-standard
    # ============================================================

    async def detect_reporting_fraud(self, reported_text: str,
                                      actual_behavior_log: dict) -> dict:
        """
        输入：实习生手写日报 + 后端核心行为日志
        模型：hunyuan-standard（高性价比语义对齐）
        输出：一致性判断 + 矛盾证据

        Prompt 逻辑：对比实习生口述汇报与系统日志，
        若实习生夸大交付物，设置 is_conflict=true 并描述核心矛盾点
        """
        if not reported_text:
            return {
                "is_conflict": False,
                "conflict_detail": "",
                "confidence": 0
            }

        system_prompt = """你是一位严谨的数据审计侦探。
你的任务是对比实习生的文字汇报与系统行为日志，判断是否存在夸大或虚假汇报。
规则：
1. 如果实习生声称完成了某项工作但系统日志无对应记录，标记为冲突
2. 如果系统日志有记录但实习生未汇报，这不算冲突（只是遗漏）
3. 只标记明确矛盾，不要过度推断
4. 输出必须是严格的 JSON 格式"""

        user_prompt = f"""
实习生在腾讯文档中手写的日报/周报内容：
{reported_text}

系统自动采集的行为日志（工蜂 Commit / TAPD 任务 / CRM 跟进）：
{json.dumps(actual_behavior_log, ensure_ascii=False)}

请对比分析，以 JSON 格式返回：
{{
  "is_conflict": true/false,
  "conflict_detail": "如果存在矛盾，请用30字以内描述核心矛盾点",
  "confidence": 0.0-1.0,
  "analysis": "50字以内的分析说明"
}}
"""

        result = await self._call_hunyuan(
            system_prompt, user_prompt, model=self.model_standard
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "is_conflict": False,
                "conflict_detail": "",
                "confidence": 0,
                "analysis": "一致性校验解析失败"
            }

    # ============================================================
    # 场景三：AI 带教小抄生成 — hunyuan-standard
    # ============================================================

    async def generate_cheat_sheet(self, intern_name: str,
                                    job_family: str,
                                    risk_reason: str,
                                    behavior_log: dict) -> str:
        """
        生成 100 字以内的导师决策小抄
        模型：hunyuan-standard
        目标：系统负责洗干净数据 + 提取上下文，导师负责看一眼做决策
        """
        system_prompt = """你是一位经验丰富的实习生带教专家。
你的任务是为业务导师生成极简的"决策小抄"，帮助导师快速判断是否需要介入。
要求：
1. 100字以内，极度精炼
2. 包含：问题诊断 + 1条可操作建议
3. 不要使用"建议导师..."等客套话，直接说事
4. 风格：像资深同事在工作群里发的消息"""

        user_prompt = f"""
实习生 {intern_name}（{job_family}岗位）触发了预警：
{risk_reason}

行为日志摘要：
{json.dumps(behavior_log, ensure_ascii=False)}

请生成一条 100 字以内的带教小抄。
"""

        result = await self._call_hunyuan(
            system_prompt, user_prompt, model=self.model_standard
        )
        # 如果返回的是 JSON，尝试提取
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and "cheat_sheet" in parsed:
                return parsed["cheat_sheet"]
        except (json.JSONDecodeError, TypeError):
            pass
        return result[:200]  # 截断保护

    # ============================================================
    # 场景四：文档/PRD 质量审计（产品线）— hunyuan-pro
    # ============================================================

    async def audit_prd_quality(self, prd_text: str,
                                 review_comments: list) -> dict:
        """
        审计腾讯文档 PRD 评论反馈，识别逻辑漏洞率
        模型：hunyuan-pro
        """
        system_prompt = """你是资深产品评审专家。
你的任务是从 PRD 评审评论中提取结构化质量指标。
规则：
1. 识别评审中指出的逻辑漏洞数量
2. 判断是否涉及需求范围的重大变更
3. 输出必须是严格的 JSON 格式"""

        user_prompt = f"""
PRD 文档摘要：{prd_text[:2000]}

评审评论：
{json.dumps(review_comments, ensure_ascii=False)}

请以 JSON 格式返回：
{{
  "logic_gaps_count": 0,
  "logic_gaps_summary": "逻辑漏洞摘要",
  "has_scope_change": false,
  "scope_change_detail": "",
  "overall_quality": "高/中/低"
}}
"""

        result = await self._call_hunyuan(
            system_prompt, user_prompt, model=self.model_pro
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"logic_gaps_count": 0, "overall_quality": "未知"}

    # ============================================================
    # 场景五：销售跟进质量审计 — hunyuan-standard
    # ============================================================

    async def audit_sales_followup(self, followup_summaries: list) -> dict:
        """
        审计企微 CRM 跟进小结，验证真实回访率
        模型：hunyuan-standard
        """
        system_prompt = """你是销售管理审计专家。
分析销售实习生的 CRM 跟进记录，判断跟进质量。
规则：识别空洞的、模板化的跟进记录 vs 真实的客户互动"""

        user_prompt = f"""
销售实习生 CRM 跟进记录：
{json.dumps(followup_summaries, ensure_ascii=False)}

请以 JSON 格式返回：
{{
  "total_followups": 0,
  "genuine_followups": 0,
  "template_followups": 0,
  "genuine_rate": 0.0,
  "quality_assessment": "50字以内的跟进质量评价"
}}
"""

        result = await self._call_hunyuan(
            system_prompt, user_prompt, model=self.model_standard
        )
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"total_followups": 0, "genuine_rate": 0}

    # ============================================================
    # 场景六：AI 智能推荐（保留 MVP 功能）
    # ============================================================

    async def get_daily_recommendations(self, tasks: list,
                                         custom_tasks: list) -> list:
        """根据今日任务 + 自定义事项，匹配推荐学习资源"""
        all_tasks = (tasks or []) + (custom_tasks or [])
        if not all_tasks:
            return []

        system_prompt = """你是公司内部知识库推荐助手。
根据实习生今日任务，推荐公司内部文档/案例/录屏。"""

        user_prompt = f"""
实习生今日任务：
{json.dumps(all_tasks, ensure_ascii=False)}

请推荐 3 个学习资源，JSON 格式：
[
  {{"type": "case|doc|video", "tag": "标签", "title": "资源标题", "desc": "关联说明"}}
]
"""

        result = await self._call_hunyuan(system_prompt, user_prompt)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return []

    async def generate_weekly_insight(self, all_interns: list) -> list:
        """生成 HR 周报的 AI 洞察"""
        system_prompt = "你是HR数据分析师，擅长从数据中发现人才趋势。"

        user_prompt = f"""
本周实习生数据：
{json.dumps(all_interns, ensure_ascii=False)}

请给出 3 条洞察建议，JSON 格式：
{{"insights": ["洞察1", "洞察2", "洞察3"]}}
"""

        result = await self._call_hunyuan(system_prompt, user_prompt)
        try:
            parsed = json.loads(result)
            return parsed.get("insights", [])
        except json.JSONDecodeError:
            return []


# ============================================================
# 全局单例
# ============================================================
hunyuan_service = HunyuanAIService()
