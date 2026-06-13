"""
Pydantic 请求/响应模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


# ============================================================
# 实习生相关
# ============================================================

class InternCreate(BaseModel):
    """创建实习生"""
    name: str = Field(..., max_length=50)
    job_family: str = Field(..., description="RD / PM / SALES")
    mentor_id: int
    entry_date: date


class InternResponse(BaseModel):
    """实习生响应"""
    id: int
    name: str
    job_family: str
    mentor_id: int
    current_state: str
    recruiter_tag: str
    entry_date: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# 导师相关
# ============================================================

class MentorCreate(BaseModel):
    """创建导师"""
    name: str = Field(..., max_length=50)
    department: Optional[str] = None
    wecom_userid: Optional[str] = None


class MentorAction(BaseModel):
    """导师一键决策"""
    mentor_id: int
    intern_id: int
    action_type: str = Field(..., description="PUSH_DOC / CREATE_GROUP / RESOLVE")
    resource_id: Optional[str] = None


# ============================================================
# Webhook 相关
# ============================================================

class GongfengPREvent(BaseModel):
    """工蜂 PR 变动事件"""
    object_kind: str = "merge_request"
    event_type: str = "merge"
    user_id: int
    user_name: str
    project_id: int
    object_attributes: Optional[Dict[str, Any]] = None


class TAPDEvent(BaseModel):
    """TAPD 事件"""
    event_type: str = Field(..., description="story / bug")
    action: str = Field(..., description="create / update / close")
    workspace_id: int
    object_id: str
    owner: str
    status: str
    extra_fields: Optional[Dict[str, Any]] = None


class WeComCRMEvent(BaseModel):
    """企微 CRM 事件"""
    event_type: str = Field(..., description="call_completed / lead_updated")
    user_id: str
    call_duration: Optional[int] = 0
    lead_id: Optional[str] = None
    followup_summary: Optional[str] = None
    extra_fields: Optional[Dict[str, Any]] = None


# ============================================================
# AI 相关
# ============================================================

class CRAuditResult(BaseModel):
    """CR 审计结果"""
    has_repeated_mistakes: bool = False
    repeated_topic: str = ""
    repeat_count: int = 0
    has_architecture_issue: bool = False
    architecture_detail: str = ""
    overall_assessment: str = ""


class FraudCheckResult(BaseModel):
    """一致性校验结果"""
    is_conflict: bool = False
    conflict_detail: str = ""
    confidence: float = 0.0
    analysis: str = ""


# ============================================================
# 通知相关
# ============================================================

class MentorAlertResponse(BaseModel):
    """导师预警响应"""
    id: int
    intern_id: int
    intern_name: str
    alert_level: str
    cheat_sheet_text: str
    status: str
    created_at: Optional[str] = None
