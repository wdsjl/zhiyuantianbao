from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    code: Optional[str] = None
    openid: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    role: str = 'student'
    invite_code: Optional[str] = None


class ReferralAgentRegisterRequest(BaseModel):
    user_id: int
    display_name: Optional[str] = None


class ReferralBindRequest(BaseModel):
    user_id: int
    invite_code: str
    device_id: Optional[str] = None
    ip: Optional[str] = None


class ReferralWithdrawRequest(BaseModel):
    user_id: int
    amount: float
    pay_method: str = 'wechat'
    pay_account: str
    pay_name: Optional[str] = None


class ParentBindRequest(BaseModel):
    parent_user_id: int
    student_phone: Optional[str] = None
    bind_code: Optional[str] = None


class ProfileSaveRequest(BaseModel):
    openid: Optional[str] = None
    phone: Optional[str] = None
    role: str = 'student'
    name: Optional[str] = None
    province: str
    city: Optional[str] = None
    school_name: Optional[str] = None
    grade: Optional[str] = None
    class_name: Optional[str] = None
    exam_year: int
    exam_type: Optional[str] = '普通类'
    subject_combination: str
    score: int
    rank: int
    target_batch: str


class RecommendRequest(BaseModel):
    province: str
    batch: str
    score: int
    rank: int
    subject_combination: str
    cities: list[str] = Field(default_factory=list)
    school_types: list[str] = Field(default_factory=list)
    major_types: list[str] = Field(default_factory=list)
    only_public: Optional[bool] = None
    accept_adjustment: bool = True
    plan_style: str = 'balanced'
    volunteer_count: int = 0
    student_id: Optional[int] = None
    auto_save_draft: bool = True


class RiskInspectRequest(BaseModel):
    items: list[dict]


class DraftItem(BaseModel):
    sort_order: int
    gradient_type: str
    school_id: int
    school_name: str
    school_code: str
    major_id: int
    major_name: str
    major_code: str
    city: Optional[str] = None
    school_type: Optional[str] = None
    tuition: Optional[int] = None
    duration: Optional[str] = None
    is_adjustable: bool = True
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None
    admission_score_2025: Optional[int] = None
    admission_rank_2025: Optional[int] = None


class DraftCreateRequest(BaseModel):
    student_id: int
    draft_name: str
    province: str
    year: int
    batch: str
    score: int
    rank: int
    risk_level: Optional[str] = None
    ai_explain: Optional[str] = None
    items: list[DraftItem]


class DraftUpdateRequest(DraftCreateRequest):
    pass


class PlanExplainRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    personality: dict = Field(default_factory=dict)
    risk: dict = Field(default_factory=dict)
    items: list[dict] = Field(default_factory=list)


class PersonalityAssessmentRequest(BaseModel):
    student_id: Optional[int] = None
    user_id: Optional[int] = None
    report: dict = Field(default_factory=dict)


class CareerReportRequest(BaseModel):
    student_id: Optional[int] = None
    user_id: Optional[int] = None
    profile: dict = Field(default_factory=dict)
    personality: dict = Field(default_factory=dict)
    assessment_id: Optional[int] = None


class StudentReportRequest(BaseModel):
    student_id: Optional[int] = None
    user_id: Optional[int] = None
    profile: dict = Field(default_factory=dict)
    personality: dict = Field(default_factory=dict)
    preferences: dict = Field(default_factory=dict)
    volunteer_summary: Optional[str] = None


class ReportPdfExportRequest(BaseModel):
    student_id: int
    report_content: Optional[str] = None


class OpenRequestCreate(BaseModel):
    user_id: int
    plan_code: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    message: Optional[str] = None
    request_type: str = 'open'


class DouyinRedeemRequest(BaseModel):
    user_id: int
    coupon_code: str


class PaymentCreateRequest(BaseModel):
    user_id: int
    plan_code: str
    request_type: str = 'open'
    login_code: Optional[str] = None


class BeanConsumeReportRequest(BaseModel):
    user_id: int
    report_title: str = 'AI 报告'
