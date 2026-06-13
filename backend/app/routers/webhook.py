"""
Webhook 接收端 — 核心数据管道
对接腾讯工蜂 PR、TAPD 需求/缺陷、企微 CRM 的异步回调
"""
import hashlib
import hmac
import json
import os
from datetime import date
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import (
    RDSnapshot, SalesSnapshot, Intern, JobFamily,
    StateNode
)
from app.services.state_machine import StateMachine
from app.dependencies import get_db

router = APIRouter()

# Webhook 签名密钥（应从环境变量读取）
GONGFENG_SECRET = os.getenv("GONGFENG_WEBHOOK_SECRET", "your-secret-token")
TAPD_SECRET = os.getenv("TAPD_WEBHOOK_SECRET", "your-tapd-secret")
WECOM_CRM_SECRET = os.getenv("WECOM_CRM_SECRET", "your-wecom-crm-secret")


# ============================================================
# Pydantic 请求模型
# ============================================================

class GongfengPREvent(BaseModel):
    """工蜂 PR 变动事件"""
    object_kind: str = "merge_request"
    event_type: str = "merge"  # merge / open / close / update
    user_id: int
    user_name: str
    project_id: int
    object_attributes: Optional[Dict[str, Any]] = None


class TAPDEvent(BaseModel):
    """TAPD 需求/缺陷状态变更"""
    event_type: str  # story / bug
    action: str      # create / update / close
    workspace_id: int
    object_id: str
    owner: str
    status: str
    extra_fields: Optional[Dict[str, Any]] = None


class WeComCRMEvent(BaseModel):
    """企微 CRM 事件（外呼/线索跟进）"""
    event_type: str  # call_completed / lead_updated
    user_id: str
    call_duration: Optional[int] = 0
    lead_id: Optional[str] = None
    followup_summary: Optional[str] = None
    extra_fields: Optional[Dict[str, Any]] = None


# ============================================================
# 签名校验工具
# ============================================================

def verify_gongfeng_signature(request: Request, body: bytes) -> bool:
    """验证工蜂 Webhook 签名"""
    token = request.headers.get("X-Gitlab-Token", "")
    return token == GONGFENG_SECRET


def verify_tapd_signature(request: Request, body: bytes) -> bool:
    """验证 TAPD Webhook HMAC 签名"""
    signature = request.headers.get("X-TAPD-Signature", "")
    if not signature:
        return False
    computed = hmac.new(
        TAPD_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


# ============================================================
# 工蜂 PR Webhook
# ============================================================

@router.post("/gongfeng/pr")
async def gongfeng_pr_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    接收腾讯工蜂 PR 变动通知
    触发条件：PR 被合入 / 关闭 / 创建 / 更新
    """
    body = await request.body()

    # 签名校验（生产环境必须启用）
    # if not verify_gongfeng_signature(request, body):
    #     raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = GongfengPREvent(**payload)
    intern_id = event.user_id

    # 查找实习生
    intern = db.get(Intern, intern_id)
    if not intern or intern.job_family != JobFamily.RD:
        return {
            "success": False,
            "message": f"用户 {intern_id} 不是研发线实习生",
            "event_type": event.event_type
        }

    # 写入/更新研发快照
    today = date.today()
    snapshot = db.query(RDSnapshot).filter(
        RDSnapshot.intern_id == intern_id,
        RDSnapshot.snapshot_date == today
    ).first()

    if not snapshot:
        snapshot = RDSnapshot(
            intern_id=intern_id,
            snapshot_date=today,
            commit_count=0,
            pr_merged_count=0,
            bug_resolved_count=0,
            cr_total_comments=0,
            raw_cr_log=[]
        )
        db.add(snapshot)
        db.flush()

    # 根据事件类型更新计数器
    if event.event_type == "merge":
        snapshot.pr_merged_count += 1
        # 提取 CR 评语（如果有）
        attrs = event.object_attributes or {}
        description = attrs.get("description", "")
        if description:
            cr_logs = snapshot.raw_cr_log or []
            cr_logs.append({
                "time": str(today),
                "event": "pr_merged",
                "description": description[:500]
            })
            snapshot.raw_cr_log = cr_logs

    elif event.event_type == "open":
        snapshot.commit_count += 1

    db.commit()

    # 触发状态机判定
    sm = StateMachine(db)
    result = sm.process_rd_event(intern_id, "FIRST_PR_MERGED")

    return {
        "success": True,
        "message": "PR 事件已处理",
        "snapshot_updated": True,
        "state_machine_result": result
    }


# ============================================================
# TAPD 需求/缺陷 Webhook
# ============================================================

@router.post("/tapd/story")
async def tapd_story_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    接收 TAPD 需求/缺陷状态变更
    自动更新通关计数
    """
    body = await request.body()

    # if not verify_tapd_signature(request, body):
    #     raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = TAPDEvent(**payload)

    # 通过 owner 字段匹配实习生
    intern = db.query(Intern).filter(
        Intern.name == event.owner
    ).first()

    if not intern:
        return {
            "success": False,
            "message": f"未找到匹配的实习生: {event.owner}"
        }

    today = date.today()

    if intern.job_family == JobFamily.RD:
        snapshot = db.query(RDSnapshot).filter(
            RDSnapshot.intern_id == intern.id,
            RDSnapshot.snapshot_date == today
        ).first()

        if not snapshot:
            snapshot = RDSnapshot(
                intern_id=intern.id,
                snapshot_date=today,
                commit_count=0,
                pr_merged_count=0,
                bug_resolved_count=0,
                cr_total_comments=0,
                raw_cr_log=[]
            )
            db.add(snapshot)
            db.flush()

        if event.event_type == "bug" and event.action == "close":
            snapshot.bug_resolved_count += 1
            event_type = "FIRST_BUG_RESOLVED"
        elif event.event_type == "story" and event.action == "close":
            event_type = "DELIVERY_ON_TIME_3_WEEKS"
        else:
            event_type = "TAPD_UPDATE"

        db.commit()

        # 触发状态机
        sm = StateMachine(db)
        result = sm.process_rd_event(intern.id, event_type)

    elif intern.job_family == JobFamily.PM:
        # 产品线：TAPD story close = PRD 评审通过
        sm = StateMachine(db)
        result = sm.process_pm_event(intern.id, "FIRST_PRD_APPROVED")
    else:
        result = {"success": True, "state_changed": False}

    return {
        "success": True,
        "message": "TAPD 事件已处理",
        "intern_id": intern.id,
        "intern_name": intern.name,
        "state_machine_result": result
    }


# ============================================================
# 企微 CRM Webhook
# ============================================================

@router.post("/wecom/crm")
async def wecom_crm_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    接收企微 CRM 事件（外呼/线索跟进）
    自动更新销售线通关进度
    """
    body = await request.body()

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = WeComCRMEvent(**payload)

    # 通过 user_id 匹配实习生
    intern = db.query(Intern).filter(
        Intern.id == int(event.user_id) if event.user_id.isdigit() else None
    ).first()

    if not intern or intern.job_family != JobFamily.SALES:
        return {
            "success": False,
            "message": f"用户 {event.user_id} 不是销售线实习生"
        }

    today = date.today()
    snapshot = db.query(SalesSnapshot).filter(
        SalesSnapshot.intern_id == intern.id,
        SalesSnapshot.snapshot_date == today
    ).first()

    if not snapshot:
        snapshot = SalesSnapshot(
            intern_id=intern.id,
            snapshot_date=today,
            crm_leads_touched=0,
            effective_call_duration=0,
            raw_followup_summaries=[]
        )
        db.add(snapshot)
        db.flush()

    # 更新快照
    if event.event_type == "call_completed":
        snapshot.effective_call_duration += (event.call_duration or 0)
        event_type = "CRM_FIRST_CALL"

    elif event.event_type == "lead_updated":
        snapshot.crm_leads_touched += 1
        event_type = "CRM_SYSTEM_FAMILIAR"

        # 保存跟进小结
        if event.followup_summary:
            summaries = snapshot.raw_followup_summaries or []
            summaries.append({
                "time": str(today),
                "summary": event.followup_summary
            })
            snapshot.raw_followup_summaries = summaries
    else:
        event_type = "CRM_UPDATE"

    db.commit()

    # 触发状态机
    sm = StateMachine(db)
    result = sm.process_sales_event(intern.id, event_type)

    return {
        "success": True,
        "message": "CRM 事件已处理",
        "intern_id": intern.id,
        "state_machine_result": result
    }


# ============================================================
# 查询接口：获取实习生状态机状态
# ============================================================

@router.get("/state/{intern_id}")
async def get_state(intern_id: int, db: Session = Depends(get_db)):
    """查询实习生当前状态机状态"""
    sm = StateMachine(db)
    return sm.get_intern_state(intern_id)


@router.post("/risk-check/{intern_id}")
async def risk_check(intern_id: int, db: Session = Depends(get_db)):
    """手动触发红灯风险检测"""
    sm = StateMachine(db)
    result = sm.detect_risk(intern_id)
    return result or {"intern_id": intern_id, "risk_detected": False}
