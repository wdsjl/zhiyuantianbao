from bootstrap_secrets import load_ecosystem_secrets

load_ecosystem_secrets()

import json
from urllib.parse import quote

from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import Response, RedirectResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from db import get_connection, rows_to_dicts, row_to_dict
from schemas import (
    RecommendRequest, RiskInspectRequest, DraftCreateRequest, ProfileSaveRequest, LoginRequest,
    ParentBindRequest, DraftUpdateRequest, PlanExplainRequest, OpenRequestCreate, PaymentCreateRequest,
    ReferralAgentRegisterRequest, ReferralBindRequest, ReferralWithdrawRequest,
    PersonalityAssessmentRequest, CareerReportRequest, StudentReportRequest, ReportPdfExportRequest,
    BeanConsumeReportRequest, DouyinRedeemRequest,
)
from student_report_service import (
    ensure_student_report_tables, save_student_report, get_latest_student_report, build_student_report_prompt,
    merge_report_inputs_from_db,
)
from province_rules_service import (
    ensure_province_rules_seeded, normalize_volunteer_override, resolve_volunteer_slots, summarize_province_rules,
)
from recommend_service import (
    attach_admission_year_stats,
    ensure_draft_item_admission_columns,
    fetch_recommendation_candidates,
    save_auto_recommendation_draft,
)
from personality_service import (
    ensure_personality_tables, save_assessment, get_latest_assessment, save_ai_career_report,
    build_personality_ai_context, build_career_report_prompt,
)
from services import get_gradient_type, get_risk_level, get_risk_reason, inspect_plan_risk, matches_subject_requirement
from rank_strategy_service import (
    assemble_recommendation_plan, detect_segment, estimate_rank_from_score, AI_STRATEGY_PROMPT,
)
from import_service import parse_import_file, import_admission_rows
from admin_views import (
    admin_home, admin_import, admin_logs, admin_schools, admin_majors, admin_admissions,
    admin_students, admin_data_sources, admin_llm_settings, admin_membership_plans,
    admin_membership_users, admin_membership_usage, admin_payments,
    admin_enrollment_plans, admin_province_rules, admin_login, admin_account, admin_crawler,
    admin_referrals, admin_referral_withdrawals, admin_score_segments, admin_announcements,
)
from crawler_service import (
    crawl_and_import, crawl_and_import_years, import_schools_only, ensure_crawl_tables,
    default_recent_years, run_crawl_job, crawl_all_provinces, has_running_crawl,
)
from crawler_config import get_preset
from henan_admission_crawler_service import run_henan_admission_crawl, run_henan_preset_job
from admin_auth_service import (
    ensure_admin_auth, verify_session_token, verify_admin_credentials,
    create_session_token, session_cookie_options, ADMIN_SESSION_COOKIE, change_admin_password,
)
from admin_data_service import (
    save_school, delete_school, save_major, delete_major, save_admission, delete_admission,
    save_enrollment_plan, delete_enrollment_plan, save_student, export_students_csv,
    save_province_rule, delete_province_rule,
)
from llm_settings_service import save_llm_settings, get_llm_settings, test_llm_connection, chat_completion
from data_fetch_service import create_source, fetch_source, list_sources, list_tasks, list_records, update_source, delete_source, review_record, archive_record_to_brochure
from auth_service import login_or_create_user, is_temp_openid, get_wechat_login_status
from pdf_service import (
    append_ai_generated_notice, build_draft_pdf, build_text_report_pdf,
    build_student_pdf_filename, pdf_content_disposition,
)
from membership_service import ensure_membership_tables, save_plan, save_plan_permission, grant_membership, revoke_membership, get_user_entitlements, list_plans, check_permission, consume_permission, reset_permission_usage, delete_permission_usage, adjust_permission_usage, export_permission_usage_csv, expire_overdue_memberships
from payment_service import ensure_payment_tables, create_manual_order, create_open_request, create_order_from_request, cancel_open_request, list_user_open_requests, list_user_orders, get_support_contact, save_support_contact, export_orders_csv, export_open_requests_csv, refund_order
from wechat_pay_service import create_wechat_payment, handle_wechat_pay_notify, sync_wechat_order_status, is_wechat_pay_ready
from referral_service import (
    ensure_referral_tables, register_agent, get_agent_dashboard, bind_invitee,
    poster_image_base64, get_binding_for_user, save_referral_settings, update_agent_commission_rate,
)

app = FastAPI(title='智愿填报 API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith('/admin') and path != '/admin/login':
            if not verify_session_token(request.cookies.get(ADMIN_SESSION_COOKIE)):
                next_path = path
                if request.url.query:
                    next_path = f'{path}?{request.url.query}'
                return RedirectResponse(f'/admin/login?next={quote(next_path)}', status_code=303)
        return await call_next(request)


app.add_middleware(AdminAuthMiddleware)


def ensure_draft_ai_column() -> None:
    with get_connection() as connection:
        columns = [row['name'] for row in connection.execute('PRAGMA table_info(volunteer_drafts)').fetchall()]
        if 'ai_explain' not in columns:
            connection.execute('ALTER TABLE volunteer_drafts ADD COLUMN ai_explain TEXT')
            connection.commit()


ensure_draft_ai_column()
ensure_draft_item_admission_columns()
ensure_membership_tables()
ensure_payment_tables()
ensure_admin_auth()
ensure_crawl_tables()
ensure_personality_tables()
ensure_student_report_tables()
from bean_service import ensure_bean_tables, sync_plan_catalog
ensure_bean_tables()
ensure_referral_tables()
from referral_p1 import ensure_referral_p1_tables
ensure_referral_p1_tables()
sync_plan_catalog()
from douyin_coupon_service import ensure_douyin_coupon_tables
ensure_douyin_coupon_tables()
ensure_province_rules_seeded()
from score_segment_service import ensure_score_segment_tables
ensure_score_segment_tables()
from user_flags_service import ensure_user_flags
ensure_user_flags()
expire_overdue_memberships()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/admin/login')
def admin_login_page(next: str = '/admin', message: str = ''):
    return admin_login(message, next)


@app.post('/admin/login')
def admin_login_submit(username: str = Form(...), password: str = Form(...), next: str = Form('/admin')):
    safe_next = next if next.startswith('/admin') and not next.startswith('/admin/login') else '/admin'
    if not verify_admin_credentials(username, password):
        return admin_login('账号或密码错误', safe_next)
    response = RedirectResponse(safe_next, status_code=303)
    response.set_cookie(ADMIN_SESSION_COOKIE, create_session_token(username), **session_cookie_options())
    return response


@app.post('/admin/logout')
def admin_logout():
    response = RedirectResponse('/admin/login', status_code=303)
    response.delete_cookie(ADMIN_SESSION_COOKIE, path='/')
    return response


@app.get('/admin/account')
def admin_account_page(message: str = ''):
    return admin_account(message)


@app.post('/admin/account/password')
def admin_account_password_change(
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    if new_password != confirm_password:
        return RedirectResponse('/admin/account?message=两次输入的新密码不一致', status_code=303)
    try:
        change_admin_password(old_password, new_password)
        response = RedirectResponse('/admin/login?message=密码已修改，请重新登录', status_code=303)
        response.delete_cookie(ADMIN_SESSION_COOKIE, path='/')
        return response
    except Exception as exc:
        return RedirectResponse(f'/admin/account?message={exc}', status_code=303)


@app.get('/admin')
def admin_index():
    return admin_home()


@app.get('/admin/crawler')
def admin_crawler_page(crawl_id: int | None = None, message: str = ''):
    return admin_crawler(message, crawl_id)


def _background_crawl_single(province: str, preset_key: str) -> None:
    try:
        run_crawl_job(province, preset_key)
    except Exception:
        pass


def _background_crawl_all(preset_key: str) -> None:
    try:
        crawl_all_provinces(preset_key)
    except Exception:
        pass


@app.post('/admin/crawler/quick')
def admin_crawler_quick(
    background_tasks: BackgroundTasks,
    province: str = Form(''),
    preset: str = Form('trial'),
):
    try:
        preset_config = get_preset(preset)
        if province:
            if has_running_crawl(province):
                return RedirectResponse(f'/admin/crawler?message={quote(f"{province} 已有采集任务在运行")}', status_code=303)
            background_tasks.add_task(_background_crawl_single, province, preset)
            message = f'{province}「{preset_config["label"]}」采集任务已在后台启动，请在采集日志查看进度'
        else:
            if has_running_crawl():
                return RedirectResponse('/admin/crawler?message=已有全国采集任务在运行', status_code=303)
            background_tasks.add_task(_background_crawl_all, preset)
            message = f'全国 31 省「{preset_config["label"]}」采集任务已在后台依次启动，耗时较长，请查看采集日志'
        return RedirectResponse(f'/admin/crawler?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/crawler?message={quote(f"启动失败：{exc}")}', status_code=303)


@app.post('/admin/crawler/run')
def admin_crawler_run(
    background_tasks: BackgroundTasks,
    province: str = Form('河南'),
    years: list[int] = Form(default=[]),
    school_limit: int = Form(0),
):
    try:
        if has_running_crawl(province):
            return RedirectResponse(f'/admin/crawler?message={quote(f"{province} 已有采集任务在运行")}', status_code=303)
        selected_years = years or default_recent_years(3)
        limit = None if school_limit == 0 else school_limit

        def job() -> None:
            try:
                if len(selected_years) == 1:
                    crawl_and_import(province, selected_years[0], limit)
                else:
                    crawl_and_import_years(province, selected_years, limit)
            except Exception:
                pass

        background_tasks.add_task(job)
        year_text = '、'.join(str(year) for year in sorted(selected_years, reverse=True))
        limit_text = '全量' if limit is None else f'{limit} 所院校'
        message = f'{province}（{year_text}，{limit_text}）采集任务已在后台启动'
        return RedirectResponse(f'/admin/crawler?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/crawler?message={quote(f"采集失败：{exc}")}', status_code=303)


@app.post('/admin/crawler/henan')
def admin_crawler_henan(background_tasks: BackgroundTasks, mode: str = Form('full')):
    try:
        if has_running_crawl('河南'):
            return RedirectResponse('/admin/crawler?message=' + quote('河南已有采集任务在运行'), status_code=303)

        def job() -> None:
            try:
                if mode == 'trial':
                    run_henan_admission_crawl(school_limit=20)
                else:
                    run_henan_preset_job()
            except Exception:
                pass

        background_tasks.add_task(job)
        label = '试跑（20校×近三年）' if mode == 'trial' else '近三年全量'
        message = f'河南录取数据「{label}」采集任务已在后台启动，请在采集日志查看进度'
        return RedirectResponse(f'/admin/crawler?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/crawler?message={quote(f"启动失败：{exc}")}', status_code=303)


@app.post('/admin/crawler/schools')
def admin_crawler_schools(background_tasks: BackgroundTasks, school_limit: int = Form(0)):
    try:
        limit = None if school_limit == 0 else school_limit
        background_tasks.add_task(import_schools_only, limit)
        message = '全国院校库同步任务已在后台启动'
        return RedirectResponse(f'/admin/crawler?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/crawler?message={quote(f"同步失败：{exc}")}', status_code=303)


@app.get('/admin/import')
def admin_import_page():
    return admin_import()


@app.post('/admin/import')
async def admin_import_submit(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows = parse_import_file(file.filename or 'upload', content)
        result = import_admission_rows(file.filename or 'upload', rows)
        plan_hint = ''
        if int(result.get('plan_only_count') or 0) > 0 and int(result.get('plan_only_count') or 0) == int(result.get('success_count') or 0):
            plan_hint = f'（均为招生计划，共 {result["plan_only_count"]} 条；智能推荐还需导入含最低分/最低位次的录取数据）'
        elif int(result.get('plan_only_count') or 0) > 0:
            plan_hint = f'（其中 {result["plan_only_count"]} 条仅招生计划）'
        message = (
            f"导入完成：共 {result['total_count']} 条，成功 {result['success_count']} 条，"
            f"失败 {result['fail_count']} 条{plan_hint}"
        )
        return admin_import(message)
    except ValueError as exc:
        return admin_import(f'导入失败：{exc}')


@app.get('/admin/import/logs')
def admin_import_logs_page(log_id: int | None = None, message: str = ''):
    return admin_logs(log_id, message)


@app.get('/admin/score-segments')
def admin_score_segments_page(message: str = ''):
    return admin_score_segments(message)


@app.post('/admin/score-segments/import')
async def admin_score_segments_import(
    file: UploadFile = File(...),
    province: str = Form('河南'),
    year: str = Form('2025'),
    batch: str = Form(''),
    subject_type: str = Form(''),
):
    from score_segment_service import import_score_segment_file

    content = await file.read()
    try:
        result = import_score_segment_file(
            content,
            file.filename or 'upload',
            province=province,
            year=int(year),
            batch=batch,
            subject_type=subject_type,
        )
        message = (
            f"一分一段导入成功：{result['province']} {result['year']}年 "
            f"{result.get('batch') or '全批次'} "
            f"{result.get('subject_type') or '不限科类'}，"
            f"共 {result['row_count']} 行，分数区间 {result['score_min']}~{result['score_max']}"
        )
        from score_segment_service import lookup_rank_by_score

        for sample_score in (680, 650):
            if result['score_min'] <= sample_score <= result['score_max']:
                sample_rank = lookup_rank_by_score(
                    result['province'],
                    sample_score,
                    year=result['year'],
                    batch=result.get('batch') or '',
                    subject_type=result.get('subject_type') or '',
                )
                if sample_rank:
                    message += f"；{sample_score}分→位次约{sample_rank}"
        return admin_score_segments(message)
    except Exception as exc:
        return admin_score_segments(f'导入失败：{exc}')


@app.get('/admin/announcements')
def admin_announcements_page(
    message: str = '',
    review_status: str = '',
    keyword: str = '',
):
    return admin_announcements(message, review_status, keyword)


@app.post('/admin/announcements/seed-portals')
def admin_announcements_seed_portals(
    province: str = Form('河南'),
    year: int = Form(2026),
    school_limit: int = Form(0),
):
    from announcement_crawler_service import seed_school_recruit_portal_links

    try:
        limit = None if int(school_limit) <= 0 else int(school_limit)
        result = seed_school_recruit_portal_links(
            province=province,
            year=int(year),
            school_limit=limit,
            only_missing=True,
        )
        message = (
            f'招生官网链接：新增 {result["created"]} 条，更新 {result["updated"]} 条，'
            f'跳过 {result["skipped"]} 条（共扫描 {result["school_total"]} 所院校）'
        )
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"生成失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/crawl')
def admin_announcements_crawl(
    background_tasks: BackgroundTasks,
    province: str = Form('河南'),
    year: int = Form(2026),
    school_limit: int = Form(200),
):
    from announcement_crawler_service import has_running_announcement_job, run_announcement_job

    try:
        if has_running_announcement_job():
            return RedirectResponse(
                '/admin/announcements?message=' + quote('已有招生公告采集任务在运行'),
                status_code=303,
            )
        limit = None if int(school_limit) <= 0 else int(school_limit)

        def job() -> None:
            try:
                run_announcement_job(
                    year=int(year),
                    province=province,
                    school_limit=limit,
                )
            except Exception:
                pass

        background_tasks.add_task(job)
        message = f'招生公告采集任务已在后台启动（{province} {year}年，院校上限 {limit or "不限"}）'
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"启动失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/approve-pending')
def admin_announcements_approve_pending(province: str = Form('河南')):
    from announcement_crawler_service import bulk_review_announcements

    try:
        count = bulk_review_announcements('approved', province=province)
        message = f'已批量通过 {count} 条待审核公告'
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"操作失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/auto-audit')
def admin_announcements_auto_audit(province: str = Form('河南')):
    from announcement_crawler_service import auto_audit_announcements

    try:
        result = auto_audit_announcements(province=province)
        message = (
            f'自动审核完成：通过 {result["approved"]} 条，驳回 {result["rejected"]} 条，'
            f'跳过保护项 {result["skipped"]} 条（共扫描 {result["scanned"]} 条）'
        )
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"自动审核失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/purge-irrelevant')
def admin_announcements_purge_irrelevant(province: str = Form('河南')):
    from announcement_crawler_service import purge_irrelevant_announcements

    try:
        result = purge_irrelevant_announcements(province=province)
        message = (
            f'已删除 {result["deleted"]} 条非招生公告，'
            f'保留招生官网链接 {result["skipped"]} 条（共扫描 {result["scanned"]} 条）'
        )
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"清理失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/{announcement_id}/delete')
def admin_announcements_delete(announcement_id: int):
    from announcement_crawler_service import delete_announcement

    try:
        deleted = delete_announcement(announcement_id)
        message = '公告已删除' if deleted else '公告不存在或已删除'
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"删除失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/create')
def admin_announcements_create(
    title: str = Form(...),
    url: str = Form(...),
    school_name: str = Form(''),
    source_org: str = Form(''),
    announcement_type: str = Form('招生公告'),
    province: str = Form('河南'),
    year: int = Form(2026),
):
    from announcement_crawler_service import create_manual_announcement

    try:
        created = create_manual_announcement(
            title=title,
            url=url,
            source_org=source_org,
            school_name=school_name,
            province=province,
            year=int(year),
            announcement_type=announcement_type,
            review_status='approved',
        )
        message = '公告已添加并审核通过' if created else '公告链接已更新'
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"添加失败：{exc}")}', status_code=303)


@app.post('/admin/announcements/{announcement_id}/review')
def admin_announcements_review(
    announcement_id: int,
    review_status: str = Form('approved'),
):
    from announcement_crawler_service import review_announcement

    try:
        review_announcement(announcement_id, review_status)
        message = '审核状态已更新'
        return RedirectResponse(f'/admin/announcements?message={quote(message)}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/announcements?message={quote(f"审核失败：{exc}")}', status_code=303)


@app.get('/admin/schools')
def admin_schools_page(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_schools(keyword, page, edit_id, message)


@app.post('/admin/schools/create')
def admin_school_create(
    school_code: str = Form(...), school_name: str = Form(...), province: str = Form(''),
    city: str = Form(''), school_type: str = Form(''), education_level: str = Form(''),
    is_985: str = Form(''), is_211: str = Form(''), is_double_first_class: str = Form(''),
    is_public: str = Form('1'), authority: str = Form(''), website: str = Form('')
):
    try:
        save_school({
            'school_code': school_code, 'school_name': school_name, 'province': province, 'city': city,
            'school_type': school_type, 'education_level': education_level,
            'is_985': bool(is_985), 'is_211': bool(is_211), 'is_double_first_class': bool(is_double_first_class),
            'is_public': bool(is_public), 'authority': authority, 'website': website
        })
        return RedirectResponse('/admin/schools?message=院校已新增', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/schools?message=保存失败：{exc}', status_code=303)


@app.post('/admin/schools/{school_id}/save')
def admin_school_update(
    school_id: int, school_code: str = Form(...), school_name: str = Form(...), province: str = Form(''),
    city: str = Form(''), school_type: str = Form(''), education_level: str = Form(''),
    is_985: str = Form(''), is_211: str = Form(''), is_double_first_class: str = Form(''),
    is_public: str = Form(''), authority: str = Form(''), website: str = Form('')
):
    try:
        save_school({
            'school_code': school_code, 'school_name': school_name, 'province': province, 'city': city,
            'school_type': school_type, 'education_level': education_level,
            'is_985': bool(is_985), 'is_211': bool(is_211), 'is_double_first_class': bool(is_double_first_class),
            'is_public': bool(is_public), 'authority': authority, 'website': website
        }, school_id)
        return RedirectResponse('/admin/schools?message=院校已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/schools?edit_id={school_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/schools/{school_id}/delete')
def admin_school_delete(school_id: int):
    try:
        delete_school(school_id)
        return RedirectResponse('/admin/schools?message=院校已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/schools?message=删除失败：{exc}', status_code=303)


@app.get('/admin/majors')
def admin_majors_page(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_majors(keyword, page, edit_id, message)


@app.post('/admin/majors/create')
def admin_major_create(
    major_code: str = Form(...), major_name: str = Form(...), major_category: str = Form(''),
    major_type: str = Form(''), degree_type: str = Form(''), duration: str = Form('')
):
    try:
        save_major({'major_code': major_code, 'major_name': major_name, 'major_category': major_category, 'major_type': major_type, 'degree_type': degree_type, 'duration': duration})
        return RedirectResponse('/admin/majors?message=专业已新增', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/majors?message=保存失败：{exc}', status_code=303)


@app.post('/admin/majors/{major_id}/save')
def admin_major_update(
    major_id: int, major_code: str = Form(...), major_name: str = Form(...), major_category: str = Form(''),
    major_type: str = Form(''), degree_type: str = Form(''), duration: str = Form('')
):
    try:
        save_major({'major_code': major_code, 'major_name': major_name, 'major_category': major_category, 'major_type': major_type, 'degree_type': degree_type, 'duration': duration}, major_id)
        return RedirectResponse('/admin/majors?message=专业已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/majors?edit_id={major_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/majors/{major_id}/delete')
def admin_major_delete(major_id: int):
    try:
        delete_major(major_id)
        return RedirectResponse('/admin/majors?message=专业已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/majors?message=删除失败：{exc}', status_code=303)


@app.get('/admin/students')
def admin_students_page(keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_students(keyword, page, edit_id, message)


@app.post('/admin/students/{student_id}/save')
def admin_student_update(
    student_id: int, name: str = Form(...), phone: str = Form(''), province: str = Form(...),
    city: str = Form(''), school_name: str = Form(''), grade: str = Form(''), class_name: str = Form(''),
    exam_year: str = Form(...), subject_combination: str = Form(...), score: str = Form(...),
    rank: str = Form(...), target_batch: str = Form(...)
):
    try:
        save_student(student_id, {
            'name': name, 'phone': phone, 'province': province, 'city': city, 'school_name': school_name,
            'grade': grade, 'class_name': class_name, 'exam_year': exam_year,
            'subject_combination': subject_combination, 'score': score, 'rank': rank, 'target_batch': target_batch
        })
        return RedirectResponse('/admin/students?message=学生档案已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/students?edit_id={student_id}&message=保存失败：{exc}', status_code=303)


@app.get('/admin/students/export')
def admin_students_export(keyword: str = ''):
    csv_text = export_students_csv(keyword)
    return Response(
        content=csv_text.encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="students.csv"'}
    )



@app.get('/admin/membership/plans')
def admin_membership_plans_page(message: str = ''):
    return admin_membership_plans(message)


@app.post('/admin/membership/plans/save')
def admin_membership_plan_save(
    plan_code: str = Form(...),
    plan_name: str = Form(...),
    price: str = Form('0'),
    duration_days: str = Form('0'),
    is_active: str = Form(''),
    sort_order: str = Form('0'),
    description: str = Form('')
):
    save_plan({
        'plan_code': plan_code,
        'plan_name': plan_name,
        'price': price,
        'duration_days': duration_days,
        'is_active': bool(is_active),
        'sort_order': sort_order,
        'description': description
    })
    return RedirectResponse('/admin/membership/plans?message=套餐已保存', status_code=303)


@app.post('/admin/membership/permissions/save')
def admin_membership_permission_save(
    plan_code: str = Form(...),
    permission_code: str = Form(...),
    is_enabled: str = Form(''),
    limit_value: str = Form('0'),
    remark: str = Form('')
):
    save_plan_permission(plan_code, permission_code, bool(is_enabled), int(limit_value or 0), remark)
    return RedirectResponse('/admin/membership/plans?message=权限已保存', status_code=303)


@app.get('/admin/membership/users')
def admin_membership_users_page(keyword: str = '', message: str = ''):
    return admin_membership_users(keyword, message)


@app.post('/admin/membership/users/grant')
def admin_membership_user_grant(
    user_id: int = Form(...),
    plan_code: str = Form(...),
    days: str = Form(''),
    remark: str = Form('')
):
    grant_membership(user_id, plan_code, int(days) if days else None, remark)
    from bean_service import grant_plan_beans
    grant_plan_beans(user_id, plan_code, remark=remark or '后台开通会员到账星鼎豆')
    return RedirectResponse('/admin/membership/users?message=会员已开通或调整', status_code=303)


@app.post('/admin/membership/users/beans/adjust')
def admin_membership_user_beans_adjust(
    user_id: int = Form(...),
    amount: int = Form(...),
    remark: str = Form('后台调整星鼎豆'),
):
    from bean_service import adjust_beans
    try:
        adjust_beans(user_id, amount, remark)
        return RedirectResponse('/admin/membership/users?message=星鼎豆已调整', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/membership/users?message={exc}', status_code=303)


@app.post('/admin/membership/users/beans/set')
def admin_membership_user_beans_set(
    user_id: int = Form(...),
    balance: int = Form(...),
    remark: str = Form('后台设置星鼎豆余额'),
):
    from bean_service import set_bean_balance
    set_bean_balance(user_id, balance, remark)
    return RedirectResponse('/admin/membership/users?message=星鼎豆余额已设置', status_code=303)


@app.post('/admin/membership/users/super-tester')
def admin_membership_user_super_tester(
    user_id: int = Form(...),
    enabled: int = Form(0),
):
    from user_flags_service import set_super_tester
    try:
        set_super_tester(user_id, bool(enabled))
        label = '已设为超级测试账号' if enabled else '已取消超级测试账号'
        return RedirectResponse(f'/admin/membership/users?message={label}', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/membership/users?message={exc}', status_code=303)


@app.post('/admin/membership/users/revoke')
def admin_membership_user_revoke(user_id: int = Form(...), remark: str = Form('')):
    revoke_membership(user_id, remark)
    return RedirectResponse('/admin/membership/users?message=会员已撤销', status_code=303)




@app.get('/admin/payments')
def admin_payments_page(keyword: str = '', message: str = ''):
    return admin_payments(keyword, message)


@app.get('/admin/referrals')
def admin_referrals_page(keyword: str = '', message: str = ''):
    return admin_referrals(keyword, message=message)


@app.post('/admin/referrals/settle')
def admin_referrals_settle(commission_id: int = Form(...)):
    from referral_service import settle_commission
    try:
        settle_commission(commission_id)
        return RedirectResponse('/admin/referrals?message=分账已确认结算', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/referrals?message=分账失败：{exc}', status_code=303)


@app.post('/admin/referrals/settings')
def admin_referrals_settings(commission_rate: float = Form(...)):
    try:
        save_referral_settings(commission_rate)
        return RedirectResponse('/admin/referrals?message=默认分账比例已保存', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/referrals?message=保存失败：{exc}', status_code=303)


@app.post('/admin/referrals/agent-rate')
def admin_referrals_agent_rate(agent_id: int = Form(...), commission_rate: float = Form(...)):
    try:
        update_agent_commission_rate(agent_id, commission_rate)
        return RedirectResponse('/admin/referrals?message=博主分账比例已更新', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/referrals?message=更新失败：{exc}', status_code=303)


@app.post('/admin/referrals/policy')
def admin_referrals_policy(
    commission_rate: float = Form(...),
    attribution_mode: str = Form('permanent'),
    attribution_days: int = Form(30),
    settlement_cycle: str = Form('monthly'),
    min_withdraw_amount: float = Form(10),
):
    from referral_p1 import save_referral_policy_settings
    save_referral_policy_settings({
        'commission_rate': commission_rate,
        'attribution_mode': attribution_mode,
        'attribution_days': attribution_days,
        'settlement_cycle': settlement_cycle,
        'min_withdraw_amount': min_withdraw_amount,
    })
    return RedirectResponse('/admin/referrals?message=推广策略已保存', status_code=303)


@app.post('/admin/referrals/agent-blacklist')
def admin_referrals_agent_blacklist(agent_id: int = Form(...), blacklisted: int = Form(1)):
    from referral_p1 import set_agent_blacklist
    set_agent_blacklist(agent_id, bool(blacklisted))
    label = '已拉黑达人' if blacklisted else '已解除拉黑'
    return RedirectResponse(f'/admin/referrals?message={label}', status_code=303)


@app.post('/admin/referrals/commission-adjust')
def admin_referrals_commission_adjust(commission_id: int = Form(...), commission_amount: float = Form(...), remark: str = Form('')):
    from referral_p1 import adjust_commission_amount
    try:
        adjust_commission_amount(commission_id, commission_amount, remark)
        return RedirectResponse('/admin/referrals?message=佣金已调整', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/referrals?message=调整失败：{exc}', status_code=303)


@app.get('/admin/referrals/export')
def admin_referrals_export():
    from referral_p1 import export_referral_csv
    csv_text = export_referral_csv()
    return Response(
        content=csv_text.encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="referral_commissions.csv"'}
    )


@app.get('/admin/referrals/withdrawals')
def admin_referral_withdrawals_page(keyword: str = '', message: str = ''):
    return admin_referral_withdrawals(keyword, message)


@app.post('/admin/referrals/withdrawals/review')
def admin_referral_withdrawals_review(withdrawal_id: int = Form(...), action: str = Form(...), remark: str = Form('')):
    from referral_p1 import review_withdrawal
    try:
        review_withdrawal(withdrawal_id, action, remark)
        return RedirectResponse('/admin/referrals/withdrawals?message=提现审核已更新', status_code=303)
    except ValueError as exc:
        return RedirectResponse(f'/admin/referrals/withdrawals?message=审核失败：{exc}', status_code=303)


@app.get('/admin/payments/requests/export')
def admin_payment_requests_export(status: str = ''):
    csv_text = export_open_requests_csv(status)
    filename = 'membership_open_requests.csv'
    return Response(
        content=csv_text.encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.get('/admin/payments/export')
def admin_payments_export(keyword: str = ''):
    csv_text = export_orders_csv(keyword)
    filename = 'payment_orders.csv'
    return Response(
        content=csv_text.encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.post('/admin/payments/support-contact')
def admin_payment_support_contact_save(
    support_wechat: str = Form(''),
    support_phone: str = Form(''),
    support_note: str = Form('')
):
    save_support_contact({
        'support_wechat': support_wechat,
        'support_phone': support_phone,
        'support_note': support_note
    })
    return RedirectResponse('/admin/payments?message=客服联系方式已保存', status_code=303)


@app.post('/admin/payments/create')
def admin_payment_create(
    user_id: int = Form(...),
    plan_code: str = Form(...),
    amount: str = Form('0'),
    days: str = Form(''),
    pay_method: str = Form('manual'),
    payer_name: str = Form(''),
    payer_contact: str = Form(''),
    remark: str = Form(''),
    order_type: str = Form('manual'),
    redirect_to: str = Form('/admin/payments')
):
    create_manual_order({
        'user_id': user_id,
        'plan_code': plan_code,
        'amount': amount,
        'days': days,
        'pay_method': pay_method,
        'payer_name': payer_name,
        'payer_contact': payer_contact,
        'remark': remark,
        'order_type': order_type,
        'auto_open': True
    })
    target = '/admin/membership/users' if redirect_to == '/admin/membership/users' else '/admin/payments'
    message = '续费订单已生成，会员已延长' if target == '/admin/membership/users' else '收款已登记，会员已开通'
    return RedirectResponse(f'{target}?message={message}', status_code=303)



@app.post('/admin/payments/requests/confirm')
def admin_payment_request_confirm(
    request_id: int = Form(...),
    amount: str = Form('0'),
    pay_method: str = Form('manual')
):
    create_order_from_request(request_id, float(amount or 0), pay_method, '小程序开通申请确认收款')
    return RedirectResponse('/admin/payments?message=开通申请已确认，订单已生成，会员已开通', status_code=303)


@app.post('/admin/payments/requests/cancel')
def admin_payment_request_cancel(request_id: int = Form(...)):
    cancel_open_request(request_id)
    return RedirectResponse('/admin/payments?message=开通申请已取消', status_code=303)


@app.post('/admin/payments/{order_id}/refund')
def admin_payment_refund(order_id: int, remark: str = Form('')):
    try:
        result = refund_order(order_id, remark)
        return RedirectResponse(f'/admin/payments?message={result.get("message", "订单已退款")}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/payments?message=退款失败：{exc}', status_code=303)


@app.get('/admin/membership/usage')
def admin_membership_usage_page(keyword: str = '', message: str = ''):
    return admin_membership_usage(keyword, message)


@app.post('/admin/membership/usage/reset')
def admin_membership_usage_reset(usage_id: int = Form(...)):
    reset_permission_usage(usage_id)
    return RedirectResponse('/admin/membership/usage?message=次数已清零', status_code=303)


@app.post('/admin/membership/usage/delete')
def admin_membership_usage_delete(usage_id: int = Form(...)):
    delete_permission_usage(usage_id)
    return RedirectResponse('/admin/membership/usage?message=次数记录已删除', status_code=303)


@app.post('/admin/membership/usage/adjust')
def admin_membership_usage_adjust(usage_id: int = Form(...), delta: int = Form(...)):
    adjust_permission_usage(usage_id, delta)
    return RedirectResponse('/admin/membership/usage?message=次数已调整', status_code=303)


@app.get('/admin/membership/usage/export')
def admin_membership_usage_export(keyword: str = ''):
    csv_text = export_permission_usage_csv(keyword)
    return Response(
        content=csv_text.encode('utf-8-sig'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="permission_usage.csv"'}
    )





@app.get('/api/membership/support-contact')
def api_membership_support_contact():
    return get_support_contact()


@app.get('/api/membership/my-status')
def api_membership_my_status(user_id: int):
    return {
        'requests': list_user_open_requests(user_id),
        'orders': list_user_orders(user_id)
    }


@app.get('/api/payments/wechat/status')
def api_wechat_pay_status():
    from wechat_virtual_pay_service import get_virtual_pay_status
    return get_virtual_pay_status()


@app.post('/api/payments/wechat/create')
def api_wechat_pay_create(payload: PaymentCreateRequest):
    try:
        return create_wechat_payment(
            payload.user_id,
            payload.plan_code,
            payload.request_type,
            payload.login_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/payments/wechat/orders/{order_no}')
def api_wechat_pay_order_status(order_no: str, user_id: int):
    try:
        return sync_wechat_order_status(order_no, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/payments/wechat/notify')
async def api_wechat_pay_notify(request: Request):
    body = await request.body()
    try:
        result = handle_wechat_pay_notify(dict(request.headers), body.decode('utf-8'))
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({'code': 'FAIL', 'message': str(exc)}, status_code=500)


@app.get('/api/douyin/status')
def api_douyin_status():
    from douyin_service import get_douyin_status
    return get_douyin_status()


@app.get('/api/douyin/landing/links')
def api_douyin_landing_links(
    page: str = Query('home'),
    page_path: str = Query(''),
    query: str = Query(''),
    invite: str = Query(''),
    from_source: str = Query('douyin', alias='from'),
    env_version: str = Query('release'),
):
    """生成抖音落地页与唤起微信小程序的跳转链接。"""
    from douyin_landing_service import generate_douyin_landing_links
    try:
        return generate_douyin_landing_links(
            page=page,
            page_path=page_path,
            query=query,
            invite=invite,
            from_source=from_source,
            env_version=env_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/douyin/landing')
def douyin_landing_page(
    page: str = Query('home'),
    page_path: str = Query(''),
    query: str = Query(''),
    invite: str = Query(''),
    from_source: str = Query('douyin', alias='from'),
    env_version: str = Query('release'),
):
    """抖音 H5 落地页：点击后唤起微信小程序。"""
    from douyin_landing_service import generate_douyin_landing_links, render_landing_page_html
    try:
        payload = generate_douyin_landing_links(
            page=page,
            page_path=page_path,
            query=query,
            invite=invite,
            from_source=from_source,
            env_version=env_version,
        )
        html = render_landing_page_html(
            title=payload['title'],
            subtitle=payload['subtitle'],
            url_scheme=payload['url_scheme'],
            url_link=payload['url_link'],
            invite=payload.get('invite') or '',
        )
        return HTMLResponse(html)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/douyin/redeem-hint')
def api_douyin_redeem_hint(code: str = ''):
    return {
        'message': '请打开微信小程序「智愿填报」→ 会员中心 → 抖音券兑换，输入券码完成开通。',
        'coupon_code': (code or '').strip().upper(),
    }


@app.post('/api/douyin/redeem')
def api_douyin_redeem(payload: DouyinRedeemRequest):
    from douyin_coupon_service import redeem_coupon
    try:
        return redeem_coupon(payload.user_id, payload.coupon_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/douyin/spi/coupon/issue')
async def api_douyin_spi_coupon_issue(request: Request):
    """抖音三方发券 SPI：用户抖店/来客下单后，抖音回调此接口获取兑换码。"""
    from douyin_service import get_douyin_config
    from douyin_coupon_service import issue_coupons_from_spi
    body = await request.body()
    try:
        payload = json.loads(body.decode('utf-8') or '{}')
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail='请求体不是合法 JSON') from exc

    config = get_douyin_config()
    client_key = (request.headers.get('x-life-clientkey') or '').strip()
    if config['spi_token']:
        token = (request.headers.get('x-douyin-spi-token') or request.headers.get('authorization') or '').strip()
        if token.startswith('Bearer '):
            token = token[7:].strip()
        if token != config['spi_token']:
            raise HTTPException(status_code=401, detail='SPI 鉴权失败')
    elif config['app_id'] and client_key and client_key != config['app_id']:
        raise HTTPException(status_code=401, detail='client_key 不匹配')

    try:
        return issue_coupons_from_spi(payload if isinstance(payload, dict) else {})
    except ValueError as exc:
        return {
            'data': {
                'error_code': 1,
                'description': str(exc),
                'result': 2,
            }
        }


@app.post('/api/payments/virtual/deliver-notify')
async def api_virtual_deliver_notify(request: Request):
    from wechat_virtual_pay_service import handle_virtual_deliver_notify
    body = await request.body()
    try:
        result = handle_virtual_deliver_notify(body.decode('utf-8'))
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({'ErrCode': -1, 'ErrMsg': str(exc)}, status_code=500)


@app.post('/api/membership/open-requests')
def api_membership_open_request(payload: OpenRequestCreate):
    result = create_open_request(payload.model_dump())
    if result.get('duplicate'):
        return {
            'request_id': result['request_id'],
            'duplicate': True,
            'request': result.get('request'),
            'message': '您已提交该套餐开通申请，请等待客服处理'
        }
    return {
        'request_id': result['request_id'],
        'duplicate': False,
        'message': '开通申请已提交，客服确认收款后会为您开通会员'
    }


@app.get('/api/membership/plans')
def api_membership_plans():
    from bean_service import apply_plan_catalog, sync_plan_catalog
    sync_plan_catalog()
    return {
        'list': [
            apply_plan_catalog(plan)
            for plan in list_plans()
            if plan.get('is_active')
        ]
    }


@app.post('/api/membership/permissions/{permission_code}/consume')
def api_membership_permission_consume(permission_code: str, user_id: int):
    result = consume_permission(user_id, permission_code)
    if not result.get('allowed'):
        raise HTTPException(status_code=403, detail=result.get('message') or '无权限使用该功能')
    return result


@app.get('/api/membership/permissions/{permission_code}/check')
def api_membership_permission_check(permission_code: str, user_id: int | None = None):
    return check_permission(user_id, permission_code)


@app.get('/api/membership/entitlements')
def api_membership_entitlements(user_id: int | None = None):
    entitlements = get_user_entitlements(user_id)
    if user_id:
        from bean_service import get_bean_balance
        entitlements['beans'] = get_bean_balance(user_id)
    return entitlements


@app.get('/api/membership/beans')
def api_membership_beans(user_id: int):
    from bean_service import get_bean_balance, PLAN_BEAN_GRANT, REPORT_BEAN_COST
    balance = get_bean_balance(user_id)
    return {
        **balance,
        'plan_grants': PLAN_BEAN_GRANT,
        'non_refundable_notice': '星鼎豆充值后不支持退款，已消费的星鼎豆不退还。',
    }


@app.post('/api/membership/beans/consume-report')
def api_membership_consume_report_beans(payload: BeanConsumeReportRequest):
    from bean_service import consume_report_beans
    try:
        return consume_report_beans(payload.user_id, payload.report_title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/admin/admissions')
def admin_admissions_page(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_admissions(province, batch, year, keyword, page, edit_id, message)


@app.post('/admin/admissions/create')
def admin_admission_create(
    year: str = Form(...), province: str = Form(...), batch: str = Form(...),
    school_id: int = Form(...), major_id: int = Form(...),
    min_score: str = Form(''), min_rank: str = Form(''), avg_score: str = Form(''),
    avg_rank: str = Form(''), enrollment_count: str = Form('')
):
    try:
        save_admission({
            'year': year, 'province': province, 'batch': batch, 'school_id': school_id, 'major_id': major_id,
            'min_score': min_score, 'min_rank': min_rank, 'avg_score': avg_score, 'avg_rank': avg_rank,
            'enrollment_count': enrollment_count
        })
        return RedirectResponse('/admin/admissions?message=录取数据已新增', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/admissions?message=保存失败：{exc}', status_code=303)


@app.post('/admin/admissions/{admission_id}/save')
def admin_admission_update(
    admission_id: int, year: str = Form(...), province: str = Form(...), batch: str = Form(...),
    school_id: int = Form(...), major_id: int = Form(...),
    min_score: str = Form(''), min_rank: str = Form(''), avg_score: str = Form(''),
    avg_rank: str = Form(''), enrollment_count: str = Form('')
):
    try:
        save_admission({
            'year': year, 'province': province, 'batch': batch, 'school_id': school_id, 'major_id': major_id,
            'min_score': min_score, 'min_rank': min_rank, 'avg_score': avg_score, 'avg_rank': avg_rank,
            'enrollment_count': enrollment_count
        }, admission_id)
        return RedirectResponse('/admin/admissions?message=录取数据已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/admissions?edit_id={admission_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/admissions/{admission_id}/delete')
def admin_admission_delete(admission_id: int):
    try:
        delete_admission(admission_id)
        return RedirectResponse('/admin/admissions?message=录取数据已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/admissions?message=删除失败：{exc}', status_code=303)


@app.get('/admin/enrollment-plans')
def admin_enrollment_plans_page(province: str = '', batch: str = '', year: str = '', keyword: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_enrollment_plans(province, batch, year, keyword, page, edit_id, message)


@app.post('/admin/enrollment-plans/create')
def admin_enrollment_plan_create(
    year: str = Form(...), province: str = Form(...), batch: str = Form(...),
    school_id: int = Form(...), major_id: int = Form(...),
    subject_requirement: str = Form(''), enrollment_count: str = Form(''),
    tuition: str = Form(''), duration: str = Form(''), campus: str = Form(''), special_notes: str = Form('')
):
    try:
        save_enrollment_plan({
            'year': year, 'province': province, 'batch': batch, 'school_id': school_id, 'major_id': major_id,
            'subject_requirement': subject_requirement, 'enrollment_count': enrollment_count,
            'tuition': tuition, 'duration': duration, 'campus': campus, 'special_notes': special_notes
        })
        return RedirectResponse('/admin/enrollment-plans?message=招生计划已新增', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/enrollment-plans?message=保存失败：{exc}', status_code=303)


@app.post('/admin/enrollment-plans/{plan_id}/save')
def admin_enrollment_plan_update(
    plan_id: int, year: str = Form(...), province: str = Form(...), batch: str = Form(...),
    school_id: int = Form(...), major_id: int = Form(...),
    subject_requirement: str = Form(''), enrollment_count: str = Form(''),
    tuition: str = Form(''), duration: str = Form(''), campus: str = Form(''), special_notes: str = Form('')
):
    try:
        save_enrollment_plan({
            'year': year, 'province': province, 'batch': batch, 'school_id': school_id, 'major_id': major_id,
            'subject_requirement': subject_requirement, 'enrollment_count': enrollment_count,
            'tuition': tuition, 'duration': duration, 'campus': campus, 'special_notes': special_notes
        }, plan_id)
        return RedirectResponse('/admin/enrollment-plans?message=招生计划已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/enrollment-plans?edit_id={plan_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/enrollment-plans/{plan_id}/delete')
def admin_enrollment_plan_delete(plan_id: int):
    try:
        delete_enrollment_plan(plan_id)
        return RedirectResponse('/admin/enrollment-plans?message=招生计划已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/enrollment-plans?message=删除失败：{exc}', status_code=303)


@app.get('/admin/province-rules')
def admin_province_rules_page(province: str = '', year: str = '', page: int = 1, edit_id: int | None = None, message: str = ''):
    return admin_province_rules(province, year, page, edit_id, message)


@app.post('/admin/province-rules/create')
def admin_province_rule_create(
    province: str = Form(...), year: str = Form(...), batch: str = Form(...), volunteer_mode: str = Form(...),
    school_count: str = Form(''), major_count_per_school: str = Form(''),
    is_parallel_volunteer: str = Form(''), adjustment_supported: str = Form(''),
    score_priority_rule: str = Form(''), rule_description: str = Form('')
):
    try:
        save_province_rule({
            'province': province, 'year': year, 'batch': batch, 'volunteer_mode': volunteer_mode,
            'school_count': school_count, 'major_count_per_school': major_count_per_school,
            'is_parallel_volunteer': bool(is_parallel_volunteer), 'adjustment_supported': bool(adjustment_supported),
            'score_priority_rule': score_priority_rule, 'rule_description': rule_description
        })
        return RedirectResponse('/admin/province-rules?message=省份规则已新增', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/province-rules?message=保存失败：{exc}', status_code=303)


@app.post('/admin/province-rules/{rule_id}/save')
def admin_province_rule_update(
    rule_id: int, province: str = Form(...), year: str = Form(...), batch: str = Form(...), volunteer_mode: str = Form(...),
    school_count: str = Form(''), major_count_per_school: str = Form(''),
    is_parallel_volunteer: str = Form(''), adjustment_supported: str = Form(''),
    score_priority_rule: str = Form(''), rule_description: str = Form('')
):
    try:
        save_province_rule({
            'province': province, 'year': year, 'batch': batch, 'volunteer_mode': volunteer_mode,
            'school_count': school_count, 'major_count_per_school': major_count_per_school,
            'is_parallel_volunteer': bool(is_parallel_volunteer), 'adjustment_supported': bool(adjustment_supported),
            'score_priority_rule': score_priority_rule, 'rule_description': rule_description
        }, rule_id)
        return RedirectResponse('/admin/province-rules?message=省份规则已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/province-rules?edit_id={rule_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/province-rules/{rule_id}/delete')
def admin_province_rule_delete(rule_id: int):
    try:
        delete_province_rule(rule_id)
        return RedirectResponse('/admin/province-rules?message=省份规则已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/province-rules?message=删除失败：{exc}', status_code=303)




@app.get('/admin/llm-settings')
def admin_llm_settings_page(message: str = ''):
    return admin_llm_settings(message)


@app.post('/admin/llm-settings')
def admin_llm_settings_save(
    provider: str = Form('openai-compatible'),
    base_url: str = Form(''),
    api_key: str = Form(''),
    model_name: str = Form(''),
    temperature: str = Form('0.7'),
    is_enabled: str = Form(''),
    remark: str = Form('')
):
    save_llm_settings({
        'provider': provider,
        'base_url': base_url,
        'api_key': api_key,
        'model_name': model_name,
        'temperature': temperature,
        'is_enabled': bool(is_enabled),
        'remark': remark
    })
    return RedirectResponse('/admin/llm-settings?message=大模型配置已保存', status_code=303)



@app.post('/admin/llm-settings/test')
def admin_llm_settings_test(
    provider: str = Form('openai-compatible'),
    base_url: str = Form(''),
    api_key: str = Form(''),
    model_name: str = Form(''),
    temperature: str = Form('0.7'),
    is_enabled: str = Form(''),
    remark: str = Form('')
):
    save_llm_settings({
        'provider': provider,
        'base_url': base_url,
        'api_key': api_key,
        'model_name': model_name,
        'temperature': temperature,
        'is_enabled': bool(is_enabled),
        'remark': remark
    })
    try:
        result = test_llm_connection()
        return RedirectResponse(f'/admin/llm-settings?message=连接成功：{result["message"]}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/llm-settings?message=连接失败：{str(exc)}', status_code=303)


@app.post('/api/llm-settings/test')
def api_llm_settings_test():
    try:
        return test_llm_connection()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/llm-settings')
def api_llm_settings():
    settings = get_llm_settings() or {}
    if settings.get('api_key'):
        settings['api_key'] = '***'
    return {'settings': settings}


@app.get('/admin/data-sources')
def admin_data_sources_page(keyword: str = '', review_status: str = '', edit_id: int | None = None, message: str = ''):
    return admin_data_sources(keyword, review_status, edit_id, message)


@app.post('/admin/data-sources')
def admin_data_sources_create(
    school_name: str = Form(...),
    school_code: str = Form(''),
    source_name: str = Form(''),
    data_type: str = Form('招生信息'),
    year: str = Form(''),
    province: str = Form(''),
    url: str = Form(...),
    remark: str = Form('')
):
    create_source({
        'school_name': school_name,
        'school_code': school_code,
        'source_name': source_name,
        'data_type': data_type,
        'year': int(year) if year.isdigit() else None,
        'province': province,
        'url': url,
        'remark': remark
    })
    return RedirectResponse('/admin/data-sources?message=数据源已新增', status_code=303)


@app.post('/admin/data-sources/{source_id}/fetch')
def admin_data_sources_fetch(source_id: int):
    try:
        result = fetch_source(source_id)
        return RedirectResponse(f'/admin/data-sources?message=采集完成，发现 {result["matched_count"]} 个链接', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/data-sources?message=采集失败：{str(exc)}', status_code=303)


@app.post('/admin/data-sources/{source_id}/save')
def admin_data_source_update(
    source_id: int, school_name: str = Form(...), school_code: str = Form(''), source_name: str = Form(''),
    data_type: str = Form('招生信息'), year: str = Form(''), province: str = Form(''),
    url: str = Form(...), remark: str = Form(''), is_active: str = Form('')
):
    try:
        update_source(source_id, {
            'school_name': school_name, 'school_code': school_code, 'source_name': source_name,
            'data_type': data_type, 'year': year, 'province': province, 'url': url,
            'remark': remark, 'is_active': bool(is_active)
        })
        return RedirectResponse('/admin/data-sources?message=数据源已更新', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/data-sources?edit_id={source_id}&message=保存失败：{exc}', status_code=303)


@app.post('/admin/data-sources/{source_id}/delete')
def admin_data_source_delete(source_id: int):
    try:
        delete_source(source_id)
        return RedirectResponse('/admin/data-sources?message=数据源已删除', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/data-sources?message=删除失败：{exc}', status_code=303)


@app.post('/admin/data-sources/records/{record_id}/review')
def admin_data_record_review(record_id: int, review_status: str = Form(...)):
    try:
        review_record(record_id, review_status)
        label = '已通过' if review_status == 'approved' else ('已驳回' if review_status == 'rejected' else '已更新')
        return RedirectResponse(f'/admin/data-sources?message=审核记录{label}', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/data-sources?message=审核失败：{exc}', status_code=303)


@app.post('/admin/data-sources/records/{record_id}/archive')
def admin_data_record_archive(record_id: int):
    try:
        brochure_id = archive_record_to_brochure(record_id)
        return RedirectResponse(f'/admin/data-sources?message=已归档到招生章程库（ID {brochure_id}）', status_code=303)
    except Exception as exc:
        return RedirectResponse(f'/admin/data-sources?message=归档失败：{exc}', status_code=303)


@app.get('/api/data-sources')
def api_data_sources(keyword: str = ''):
    return {'list': list_sources(keyword)}


@app.post('/api/data-sources/{source_id}/fetch')
def api_data_source_fetch(source_id: int):
    try:
        return fetch_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/data-fetch/tasks')
def api_data_fetch_tasks(source_id: int | None = None):
    return {'list': list_tasks(source_id)}


@app.get('/api/data-fetch/records')
def api_data_fetch_records(task_id: int | None = None, source_id: int | None = None):
    return {'list': list_records(task_id, source_id)}


@app.get('/api/auth/wechat/status')
def api_wechat_login_status():
    return get_wechat_login_status()


@app.post('/api/auth/login')
def login(request: LoginRequest):
    try:
        return login_or_create_user(
            request.code, request.openid, request.phone, request.name, request.role, request.invite_code
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/referral/agent/register')
def api_referral_agent_register(request: ReferralAgentRegisterRequest):
    try:
        agent = register_agent(request.user_id, request.display_name)
        return {'agent': agent}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/referral/dashboard')
def api_referral_dashboard(user_id: int = Query(...)):
    try:
        return get_agent_dashboard(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/referral/poster')
def api_referral_poster(user_id: int = Query(...)):
    try:
        agent = register_agent(user_id)
        image_base64 = poster_image_base64(agent['invite_code'], agent.get('display_name') or '')
        return {
            'invite_code': agent['invite_code'],
            'display_name': agent.get('display_name'),
            'commission_rate': agent.get('commission_rate'),
            'image_base64': image_base64,
            'share_path': f'pages/home/home?invite={agent["invite_code"]}',
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/referral/bind')
def api_referral_bind(request: ReferralBindRequest):
    from referral_p1 import attempt_bind_invitee, claim_free_trial_once
    result = attempt_bind_invitee(
        request.user_id,
        request.invite_code,
        'scan',
        ip=request.ip or '',
        device_id=request.device_id or '',
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('message') or '绑定失败')
    with get_connection() as connection:
        user = row_to_dict(connection.execute('SELECT openid FROM users WHERE user_id = ?', [request.user_id]).fetchone())
    free_claim = claim_free_trial_once(
        request.user_id,
        (user or {}).get('openid') or '',
        (result.get('agent') or {}).get('agent_id'),
        request.device_id or '',
        request.ip or '',
    )
    return {**result, 'free_claim': free_claim}


@app.get('/api/referral/my-binding')
def api_referral_my_binding(user_id: int = Query(...)):
    binding = get_binding_for_user(user_id)
    return {'binding': binding}


@app.get('/api/referral/policy')
def api_referral_policy():
    from referral_p1 import get_referral_policy_settings
    return get_referral_policy_settings()


@app.post('/api/referral/withdraw')
def api_referral_withdraw(request: ReferralWithdrawRequest):
    from referral_p1 import create_withdrawal
    agent = register_agent(request.user_id)
    try:
        withdrawal = create_withdrawal(
            int(agent['agent_id']),
            request.amount,
            request.pay_method,
            request.pay_account,
            request.pay_name or '',
        )
        return {'withdrawal': withdrawal}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/referral/withdrawals')
def api_referral_withdrawals(user_id: int = Query(...)):
    from referral_p1 import list_withdrawals
    agent = register_agent(user_id)
    rows = [item for item in list_withdrawals() if int(item.get('agent_id') or 0) == int(agent['agent_id'])]
    return {'list': rows}


@app.get('/api/referral/trace')
def api_referral_trace(keyword: str = Query(...)):
    from referral_p1 import trace_attribution
    return trace_attribution(keyword)


@app.get('/api/profile')
def get_profile(openid: str = '', phone: str = ''):
    if not openid and not phone:
        raise HTTPException(status_code=400, detail='openid 和 phone 至少提供一个')
    sql = '''
    SELECT u.user_id, u.openid, u.phone, u.role, u.name, s.student_id, s.province, s.city,
           s.school_name, s.grade, s.class_name, s.exam_year, s.exam_type,
           s.subject_combination, s.score, s.rank, s.target_batch
    FROM users u
    LEFT JOIN students s ON s.user_id = u.user_id
    WHERE 1=1
    '''
    params = []
    if openid:
        sql += ' AND u.openid = ?'
        params.append(openid)
    if phone:
        sql += ' AND u.phone = ?'
        params.append(phone)
    sql += ' ORDER BY s.student_id DESC LIMIT 1'
    with get_connection() as connection:
        profile = row_to_dict(connection.execute(sql, params).fetchone())
    if not profile:
        raise HTTPException(status_code=404, detail='档案不存在')
    return {'profile': profile}


@app.post('/api/profile')
def save_profile(request: ProfileSaveRequest):
    openid = request.openid or f'local_{request.phone or request.name or "student"}'
    role = 'student' if request.role in ['学生', 'student'] else 'parent' if request.role in ['家长', 'parent'] else request.role
    with get_connection() as connection:
        user = row_to_dict(connection.execute('SELECT user_id, openid FROM users WHERE openid = ?', [openid]).fetchone())
        if not user and request.phone:
            phone_user = row_to_dict(connection.execute('SELECT user_id, openid FROM users WHERE phone = ?', [request.phone]).fetchone())
            if phone_user and phone_user.get('openid') and phone_user.get('openid') != openid:
                phone_openid = phone_user.get('openid') or ''
                if is_temp_openid(phone_openid) and not is_temp_openid(openid):
                    user = phone_user
                elif is_temp_openid(openid) and not is_temp_openid(phone_openid):
                    user = phone_user
                    openid = phone_openid
                elif is_temp_openid(phone_openid) and is_temp_openid(openid):
                    user = phone_user
                else:
                    raise HTTPException(status_code=409, detail='该手机号已绑定其他微信账号，不能重复注册使用')
            elif phone_user:
                user = phone_user

        if user:
            user_id = user['user_id']
            connection.execute(
                'UPDATE users SET openid = ?, phone = ?, role = ?, name = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?',
                [openid, request.phone, role, request.name, user_id]
            )
        else:
            cursor = connection.execute(
                'INSERT INTO users (openid, phone, role, name) VALUES (?, ?, ?, ?)',
                [openid, request.phone, role, request.name]
            )
            user_id = cursor.lastrowid

        if role == 'parent':
            connection.commit()
            return {'user_id': user_id, 'student_id': None, 'openid': openid, 'message': '家长账号保存成功，请绑定已注册学生'}

        student = row_to_dict(connection.execute('SELECT student_id, name FROM students WHERE user_id = ?', [user_id]).fetchone())
        values = [
            request.name, request.province, request.city, request.school_name, request.grade, request.class_name,
            request.exam_year, request.exam_type, request.subject_combination, request.score, request.rank,
            request.target_batch
        ]
        if student:
            if student.get('name') and request.name and student.get('name') != request.name:
                raise HTTPException(status_code=409, detail=f'该账号已注册学生“{student.get("name")}”，不能改为其他学生使用')
            student_id = student['student_id']
            connection.execute(
                '''
                UPDATE students SET name = ?, province = ?, city = ?, school_name = ?, grade = ?, class_name = ?,
                  exam_year = ?, exam_type = ?, subject_combination = ?, score = ?, rank = ?, target_batch = ?,
                  updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
                ''',
                values + [student_id]
            )
        else:
            cursor = connection.execute(
                '''
                INSERT INTO students (
                  user_id, name, province, city, school_name, grade, class_name, exam_year, exam_type,
                  subject_combination, score, rank, target_batch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [user_id] + values
            )
            student_id = cursor.lastrowid
        connection.commit()
    return {'user_id': user_id, 'student_id': student_id, 'openid': openid, 'message': '档案保存成功'}


@app.post('/api/parent-bind')
def bind_parent_student(request: ParentBindRequest):
    if not request.student_phone and not request.bind_code:
        raise HTTPException(status_code=400, detail='学生手机号或绑定码至少填写一个')

    with get_connection() as connection:
        parent = row_to_dict(connection.execute('SELECT * FROM users WHERE user_id = ?', [request.parent_user_id]).fetchone())
        if not parent:
            raise HTTPException(status_code=404, detail='家长用户不存在')
        active_bind = row_to_dict(connection.execute(
            'SELECT bind_id, student_id FROM parent_student_binds WHERE parent_user_id = ? AND bind_status = ?',
            [request.parent_user_id, 'active']
        ).fetchone())

        sql = '''
        SELECT u.user_id AS student_user_id, s.student_id, u.phone, s.name
        FROM users u
        JOIN students s ON s.user_id = u.user_id
        WHERE 1=1
        '''
        params = []
        if request.student_phone:
            sql += ' AND u.phone = ?'
            params.append(request.student_phone)
        if request.bind_code:
            sql += ' AND (u.phone = ? OR CAST(s.student_id AS TEXT) = ?)'
            params.extend([request.bind_code, request.bind_code])
        sql += ' LIMIT 1'
        student = row_to_dict(connection.execute(sql, params).fetchone())
        if not student:
            raise HTTPException(status_code=404, detail='未找到对应学生')
        if active_bind and active_bind.get('student_id') != student['student_id']:
            raise HTTPException(status_code=409, detail='该家长账号已绑定一个学生，不能绑定多个学生使用')

        existed = row_to_dict(connection.execute(
            'SELECT bind_id FROM parent_student_binds WHERE parent_user_id = ? AND student_id = ?',
            [request.parent_user_id, student['student_id']]
        ).fetchone())
        if existed:
            bind_id = existed['bind_id']
            connection.execute('UPDATE parent_student_binds SET bind_status = ?, bind_code = ? WHERE bind_id = ?', ['active', request.bind_code, bind_id])
        else:
            cursor = connection.execute(
                '''
                INSERT INTO parent_student_binds (parent_user_id, student_user_id, student_id, bind_status, bind_code)
                VALUES (?, ?, ?, ?, ?)
                ''',
                [request.parent_user_id, student['student_user_id'], student['student_id'], 'active', request.bind_code]
            )
            bind_id = cursor.lastrowid
        connection.commit()
    return {'bind_id': bind_id, 'student_id': student['student_id'], 'student_name': student['name'], 'message': '绑定成功'}


@app.get('/api/parent-bind')
def list_parent_binds(parent_user_id: int):
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT b.bind_id, b.bind_status, b.created_at, s.student_id, s.name, s.province, s.school_name, s.class_name,
                   s.score, s.rank, s.target_batch
            FROM parent_student_binds b
            JOIN students s ON s.student_id = b.student_id
            WHERE b.parent_user_id = ? AND b.bind_status = 'active'
            ORDER BY b.created_at DESC
            ''',
            [parent_user_id]
        ).fetchall()
    return {'list': rows_to_dicts(rows)}


@app.get('/api/schools')
def list_schools(
    keyword: str = '',
    city: str = '',
    province: str = '',
    batch: str = '',
    is_public: int | None = Query(default=None),
    is_double_first_class: int | None = Query(default=None),
    limit: int = 200,
    offset: int = 0,
):
    from school_library_service import list_province_schools

    return list_province_schools(
        province,
        batch,
        keyword=keyword,
        city=city,
        is_public=is_public,
        is_double_first_class=is_double_first_class,
        limit=limit,
        offset=offset,
    )


@app.get('/api/schools/{school_id}')
def get_school(school_id: int):
    with get_connection() as connection:
        school = row_to_dict(connection.execute('SELECT * FROM schools WHERE school_id = ?', [school_id]).fetchone())
        if not school:
            raise HTTPException(status_code=404, detail='院校不存在')
        plans = rows_to_dicts(connection.execute(
            '''
            SELECT ep.*, m.major_category, m.major_type
            FROM enrollment_plans ep
            JOIN majors m ON m.major_id = ep.major_id
            WHERE ep.school_id = ?
            ORDER BY ep.year DESC, ep.batch ASC
            ''',
            [school_id]
        ).fetchall())
    return {'school': school, 'plans': plans}


@app.get('/api/majors')
def list_majors(keyword: str = '', major_type: str = '', limit: int = 50, offset: int = 0):
    sql = 'SELECT * FROM majors WHERE 1=1'
    params = []
    if keyword:
        sql += ' AND (major_name LIKE ? OR major_code LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like])
    if major_type:
        sql += ' AND major_type = ?'
        params.append(major_type)
    sql += ' ORDER BY major_id ASC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {'list': rows_to_dicts(rows)}


@app.get('/api/admissions')
def list_admissions(
    province: str = '',
    batch: str = '',
    year: int | None = None,
    school_id: int | None = None,
    major_id: int | None = None,
    keyword: str = '',
    limit: int = 100,
    offset: int = 0
):
    from recommend_service import expand_batch_aliases, province_variants

    sql = '''
    SELECT ar.*, s.school_name, s.city, s.is_public, s.is_double_first_class, m.major_name, m.major_type
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    WHERE 1=1
    '''
    params = []
    if province:
        variants = province_variants(province)
        placeholders = ','.join(['?'] * len(variants))
        sql += f' AND ar.province IN ({placeholders})'
        params.extend(variants)
    if batch:
        batch_aliases = expand_batch_aliases(batch) or [batch]
        placeholders = ','.join(['?'] * len(batch_aliases))
        sql += f' AND ar.batch IN ({placeholders})'
        params.extend(batch_aliases)
    if keyword:
        like = f'%{keyword}%'
        sql += ' AND (s.school_name LIKE ? OR m.major_name LIKE ? OR s.school_code LIKE ?)'
        params.extend([like, like, like])
    if year is not None:
        sql += ' AND ar.year = ?'
        params.append(year)
    if school_id is not None:
        sql += ' AND ar.school_id = ?'
        params.append(school_id)
    if major_id is not None:
        sql += ' AND ar.major_id = ?'
        params.append(major_id)
    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {'list': rows_to_dicts(rows)}


@app.get('/api/schools/rank-snapshot')
def school_rank_snapshot(
    province: str = Query(...),
    batch: str = '本科批',
    year: int | None = None,
    keyword: str = '',
    limit: int = 5000,
):
    from school_library_service import build_school_snapshot_map

    snapshot = build_school_snapshot_map(province, batch, year=year, keyword=keyword, limit=limit)
    rows = sorted(
        snapshot.values(),
        key=lambda item: (
            item.get('best_min_rank') is None,
            int(item.get('best_min_rank') or 10**9),
        ),
    )
    return {'list': rows, 'province': province, 'batch': batch, 'year': year, 'total': len(rows)}


@app.get('/api/score-segments/tables')
def list_score_segment_tables(province: str = '', limit: int = 20):
    from score_segment_service import list_score_rank_tables

    tables = list_score_rank_tables(limit)
    if province:
        tables = [item for item in tables if province in str(item.get('province') or '')]
    return {'list': tables}


@app.get('/api/score-segments/lookup')
def lookup_score_segment(
    province: str = Query(...),
    score: int | None = Query(None),
    rank: int | None = Query(None),
    year: int | None = Query(None),
    batch: str = Query(''),
    subject_type: str = Query(''),
    subject_combination: str = Query(''),
):
    from score_segment_service import (
        lookup_rank_by_score,
        lookup_score_by_rank,
        find_score_rank_table,
        infer_subject_type_from_combination,
    )

    if score is None and rank is None:
        raise HTTPException(status_code=400, detail='请提供 score 或 rank 参数')
    resolved_subject = subject_type or infer_subject_type_from_combination(subject_combination)
    table = find_score_rank_table(province, year, batch, resolved_subject)
    if not table and resolved_subject:
        table = find_score_rank_table(province, year, batch, '')
    if not table:
        from score_segment_service import summarize_score_tables_for_province

        available = summarize_score_tables_for_province(province)
        if not available:
            raise HTTPException(status_code=404, detail='未找到一分一段表，请先在后台导入')
        hints = []
        for row in available[:6]:
            subject = row.get('subject_type') or '不限科类'
            batch_label = row.get('batch') or '全批次'
            hints.append(f'{row.get("year")}年·{subject}·{batch_label}')
        year_hint = f'（您查询的是 {year or "不限"} 年）' if year else ''
        typed_count = sum(1 for row in available if (row.get('subject_type') or '').strip())
        subject_hint = '，请选择物理类或历史类' if typed_count > 1 and not resolved_subject else ''
        raise HTTPException(
            status_code=404,
            detail=f'未找到匹配的一分一段表{year_hint}{subject_hint}。已导入：{"；".join(hints)}',
        )
    result = {
        'province': province,
        'year': table.get('year'),
        'batch': table.get('batch') or '',
        'subject_type': table.get('subject_type') or '',
        'table_id': table.get('table_id'),
    }
    if score is not None:
        estimated_rank = lookup_rank_by_score(
            province, int(score), year=year, batch=batch, subject_type=resolved_subject
        )
        if estimated_rank is None and resolved_subject:
            estimated_rank = lookup_rank_by_score(
                province, int(score), year=year, batch=batch, subject_type=''
            )
        result['score'] = int(score)
        result['rank'] = estimated_rank
    if rank is not None:
        estimated_score = lookup_score_by_rank(
            province, int(rank), year=year, batch=batch, subject_type=resolved_subject
        )
        if estimated_score is None and resolved_subject:
            estimated_score = lookup_score_by_rank(
                province, int(rank), year=year, batch=batch, subject_type=''
            )
        result['rank'] = int(rank)
        result['score'] = estimated_score
    return result


@app.get('/api/announcements')
def api_announcements(
    keyword: str = '',
    province: str = '河南',
    school_name: str = '',
    school_id: int | None = None,
    year: int = 2026,
    henan_only: bool = False,
    review_status: str = 'approved',
    announcement_type: str = '',
    limit: int = 50,
):
    from announcement_crawler_service import search_announcements

    if school_id:
        with get_connection() as connection:
            school = row_to_dict(
                connection.execute('SELECT school_name FROM schools WHERE school_id = ?', [school_id]).fetchone()
            )
        if school and school.get('school_name'):
            school_name = school_name or school['school_name']
    return {
        'list': search_announcements(
            keyword=keyword,
            province=province,
            school_name=school_name,
            year=year,
            henan_only=henan_only,
            review_status=review_status,
            announcement_type=announcement_type,
            limit=limit,
        )
    }


@app.get('/api/announcements/{announcement_id}')
def api_announcement_detail(announcement_id: int):
    from announcement_crawler_service import get_announcement

    item = get_announcement(announcement_id)
    if not item:
        raise HTTPException(status_code=404, detail='公告不存在')
    if item.get('review_status') != 'approved':
        raise HTTPException(status_code=403, detail='公告未通过审核')
    return item


@app.get('/api/announcements/{announcement_id}/file')
def api_announcement_file(announcement_id: int):
    from announcement_crawler_service import get_announcement
    from announcement_pdf_parser_service import download_announcement_file, guess_file_ext

    item = get_announcement(announcement_id)
    if not item:
        raise HTTPException(status_code=404, detail='公告不存在')
    if item.get('review_status') != 'approved':
        raise HTTPException(status_code=403, detail='公告未通过审核')
    file_url = item.get('file_url') or item.get('url')
    if not file_url:
        raise HTTPException(status_code=404, detail='公告文件不存在')
    try:
        content, filename = download_announcement_file(file_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'文件下载失败：{exc}') from exc
    ext = guess_file_ext(file_url, filename, content)
    media_types = {
        'pdf': 'application/pdf',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'csv': 'text/csv',
    }
    media_type = media_types.get(ext, 'application/octet-stream')
    headers = {'Content-Disposition': f'inline; filename="{filename or f"announcement.{ext or "bin"}"}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@app.get('/api/province-rules')
def list_province_rules(province: str = '', year: int | None = None, batch: str = ''):
    sql = 'SELECT * FROM province_rules WHERE 1=1'
    params = []
    if province:
        sql += ' AND province = ?'
        params.append(province)
    if year is not None:
        sql += ' AND year = ?'
        params.append(year)
    if batch:
        sql += ' AND batch = ?'
        params.append(batch)
    sql += ' ORDER BY year DESC, province ASC'
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {'list': rows_to_dicts(rows)}


@app.get('/api/admission-data/batches')
def api_admission_data_batches(province: str):
    if not province.strip():
        raise HTTPException(status_code=400, detail='请提供省份')
    from recommend_service import list_province_admission_batches

    batches = list_province_admission_batches(province)
    total = sum(int(item.get('school_major_count') or item.get('record_count') or 0) for item in batches)
    return {
        'province': province,
        'batches': batches,
        'total_school_major': total,
    }


@app.get('/api/province-rules/summary')
def province_rules_summary():
    return {'list': summarize_province_rules(), 'year': 2025}


@app.get('/api/province-rules/resolve')
def province_rules_resolve(province: str, batch: str = '', year: int = 2025):
    if not province.strip():
        raise HTTPException(status_code=400, detail='请提供省份')
    resolved = resolve_volunteer_slots(province, batch, year)
    rule = resolved['rule']
    return {
        'province': rule.get('province') or province,
        'batch': rule.get('batch') or batch,
        'requested_batch': batch,
        'year': rule.get('year') or year,
        'volunteer_mode': rule.get('volunteer_mode'),
        'school_count': rule.get('school_count'),
        'major_count_per_school': rule.get('major_count_per_school'),
        'total_slots': resolved['total_slots'],
        'matched': bool(rule.get('matched')),
        'source': resolved['source'],
        'rule_description': rule.get('rule_description') or '',
    }


@app.post('/api/recommend')
def recommend(request: RecommendRequest):
    from recommend_service import province_variants

    slot_info = resolve_volunteer_slots(
        request.province,
        request.batch,
        override_count=normalize_volunteer_override(request.volunteer_count),
    )
    total_slots = slot_info['total_slots']
    province_rule = slot_info['rule']
    rule_batch = province_rule.get('batch') or request.batch

    user_rank = int(request.rank)
    if user_rank <= 0 and request.score:
        estimated = None
        try:
            from score_segment_service import lookup_rank_by_score
            estimated = lookup_rank_by_score(
                request.province,
                int(request.score),
                year=2026,
                batch=request.batch,
            )
        except ImportError:
            pass
        if estimated:
            user_rank = estimated

    province_list = province_variants(request.province)
    province_placeholders = ','.join(['?'] * len(province_list))
    with get_connection() as connection:
        total_row = connection.execute(
            f'''
            SELECT MAX(min_rank) AS total_rank FROM admission_records
            WHERE province IN ({province_placeholders}) AND batch = ?
            ''',
            [*province_list, rule_batch],
        ).fetchone()
    province_total_rank = total_row['total_rank'] if total_row and total_row['total_rank'] else None
    segment = detect_segment(user_rank, province_total_rank, rule_batch)

    weighted_items, effective_batch, candidate_meta = fetch_recommendation_candidates(
        request.province,
        request.batch,
        request.subject_combination,
        total_slots,
        cities=request.cities,
        school_types=request.school_types,
        major_types=request.major_types,
        only_public=request.only_public,
        rule_batch=rule_batch,
        user_rank=user_rank if user_rank > 0 else None,
        segment=segment,
    )

    if user_rank <= 0 and request.score and weighted_items:
        estimated = estimate_rank_from_score(weighted_items, int(request.score))
        if estimated:
            user_rank = estimated
            segment = detect_segment(user_rank, province_total_rank, effective_batch)

    user_score = int(request.score) if request.score else None
    strategy_rank_hint = ''
    if user_score and user_rank > 0:
        try:
            from score_segment_service import lookup_rank_by_score
            expected_rank = lookup_rank_by_score(
                request.province,
                user_score,
                year=2026,
                batch=request.batch,
            )
            if expected_rank and abs(expected_rank - user_rank) > max(5000, int(user_rank * 0.5)):
                strategy_rank_hint = (
                    f'档案位次 {user_rank} 与一分一段表推算位次 {expected_rank} 差距较大，'
                    '建议核对档案或重新导入一分一段表。'
                )
        except ImportError:
            pass

    selected_rows, strategy_meta = assemble_recommendation_plan(
        weighted_items,
        user_rank=user_rank,
        plan_style=request.plan_style or 'balanced',
        batch=effective_batch,
        segment=segment,
        total_slots=total_slots,
        max_majors_per_school=province_rule.get('major_count_per_school') or 6,
        user_score=user_score,
    )
    if strategy_rank_hint:
        strategy_meta['rank_hint'] = strategy_rank_hint
    strategy_meta['volunteer_rule'] = {
        'province': province_rule.get('province') or request.province,
        'batch': province_rule.get('batch') or effective_batch,
        'requested_batch': request.batch,
        'effective_batch': effective_batch,
        'volunteer_mode': province_rule.get('volunteer_mode'),
        'school_count': province_rule.get('school_count'),
        'major_count_per_school': province_rule.get('major_count_per_school'),
        'total_slots': total_slots,
        'matched': bool(province_rule.get('matched')),
        'source': slot_info['source'],
        'rule_description': province_rule.get('rule_description') or '',
        'candidate_pool': candidate_meta.get('candidate_pool'),
        'relaxed_major_filter': candidate_meta.get('relaxed_major_filter'),
        'rank_window': candidate_meta.get('rank_window'),
        'rank_window_relaxed': candidate_meta.get('rank_window_relaxed'),
    }

    items = []
    for index, row in enumerate(selected_rows, start=1):
        gradient_type = row.get('gradient_type') or get_gradient_type(
            user_rank, row.get('weighted_rank'), segment, effective_batch
        )
        is_adjustable = request.accept_adjustment
        risk_level = get_risk_level(gradient_type, is_adjustable)
        items.append({
            'sort_order': index,
            'gradient_type': gradient_type,
            'school_id': row['school_id'],
            'school_name': row['school_name'],
            'school_code': row['school_code'],
            'major_id': row['major_id'],
            'major_name': row['major_name'],
            'major_code': row['major_code'],
            'major_type': row.get('major_type'),
            'city': row['city'],
            'school_type': row['school_type'],
            'tuition': row.get('tuition'),
            'duration': row.get('duration'),
            'min_score': row.get('min_score'),
            'min_rank': row.get('min_rank'),
            'weighted_score': row.get('weighted_score'),
            'weighted_rank': row.get('weighted_rank'),
            'years_used': row.get('years_used'),
            'admission_probability': row.get('admission_probability'),
            'is_adjustable': is_adjustable,
            'risk_level': risk_level,
            'risk_reason': get_risk_reason(gradient_type, is_adjustable)
        })

    items = attach_admission_year_stats(items, request.province, effective_batch, fallback_batch=request.batch)

    risk = inspect_plan_risk(items)
    draft_id = None
    if request.student_id and request.auto_save_draft and items:
        try:
            draft_id = save_auto_recommendation_draft(
                int(request.student_id),
                request.province,
                effective_batch,
                int(request.score),
                user_rank,
                risk.get('level') or '未排查',
                items,
            )
        except Exception:
            draft_id = None

    return {
        'items': items,
        'risk': risk,
        'strategy': strategy_meta,
        'algorithm': strategy_meta.get('algorithm'),
        'algorithm_version': strategy_meta.get('algorithm_version'),
        'generation': {
            'target_slots': total_slots,
            'generated_count': len(items),
            'candidate_pool': candidate_meta.get('candidate_pool'),
            'effective_batch': effective_batch,
            'requested_batch': candidate_meta.get('requested_batch') or request.batch,
            'batch_fallback': candidate_meta.get('batch_fallback'),
            'batch_hint': candidate_meta.get('batch_hint') or '',
            'available_batches': candidate_meta.get('available_batches') or [],
            'available_batch_counts': candidate_meta.get('available_batch_counts') or {},
            'relaxed_major_filter': bool(candidate_meta.get('relaxed_major_filter')),
            'rank_window': candidate_meta.get('rank_window'),
            'rank_window_relaxed': bool(candidate_meta.get('rank_window_relaxed')),
            'shortfall_hint': (
                f'候选池仅 {candidate_meta.get("candidate_pool")} 条，未达到目标 {total_slots} 个志愿。'
                '请补充录取数据、放宽筛选条件，或核对档案批次是否与导入数据一致。'
            ) if len(items) < total_slots else '',
        },
        'draft_id': draft_id,
    }


@app.post('/api/ai/plan-explain')
def ai_plan_explain(request: PlanExplainRequest):
    if not request.items:
        raise HTTPException(status_code=400, detail='请先生成志愿方案')
    profile = request.profile or {}
    personality = request.personality or {}
    risk = request.risk or {}
    sample_items = request.items[:12]
    item_lines = []
    for item in sample_items:
        item_lines.append(
            f"{item.get('sort_order') or item.get('sortOrder', '')}. "
            f"{item.get('gradient_type') or item.get('gradientType', '')} "
            f"{item.get('school_name') or item.get('schoolName', '')} - "
            f"{item.get('major_name') or item.get('majorName', '')}，"
            f"风险：{item.get('risk_level') or item.get('riskLevel', '')}，"
            f"调剂：{'是' if item.get('is_adjustable', item.get('isAdjustable', True)) else '否'}"
        )
    prompt = f'''
请作为高考志愿填报顾问，基于以下信息生成一份简洁、谨慎、可执行的志愿方案解读。
要求：
1. 不承诺录取，不使用“保证”“一定”等词。
2. 分为：整体评价、性格与专业适配、冲稳保结构、风险提醒、下一步建议。
3. 语言面向学生和家长，控制在 500 字以内。
4. 核心只看全省位次 X，不要以分数高低作为主要判断依据。

位次冲稳保规则：
{AI_STRATEGY_PROMPT}

学生信息：
省份：{profile.get('province', '')}
批次：{profile.get('targetBatch', profile.get('batch', ''))}
选科：{profile.get('subjectCombination', '')}
全省位次 X：{profile.get('rank', '')}

霍兰德职业兴趣测评（供专业适配参考）：
{build_personality_ai_context(personality)}

风险结果：
综合风险：{risk.get('level', '未排查')}
冲：{risk.get('chong', '')} 稳：{risk.get('wen', '')} 保：{risk.get('bao', '')} 垫：{risk.get('dian', '')}

志愿样例：
{chr(10).join(item_lines)}
'''
    try:
        content = chat_completion([
            {'role': 'system', 'content': '你是专业、谨慎的高考志愿填报顾问，所有建议必须提示以官方信息为准。'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=900)
        return {'explain': append_ai_generated_notice(content)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/personality/assessment')
def save_personality_assessment(request: PersonalityAssessmentRequest):
    if not request.report:
        raise HTTPException(status_code=400, detail='测评结果不能为空')
    assessment_id = save_assessment(request.student_id, request.user_id, request.report)
    return {'assessment_id': assessment_id, 'message': '测评报告已保存'}


@app.get('/api/personality/assessment')
def get_personality_assessment(student_id: int):
    assessment = get_latest_assessment(student_id)
    if not assessment:
        return {'assessment': None}
    return {'assessment': assessment}


@app.post('/api/ai/career-report')
def ai_career_report(request: CareerReportRequest):
    merged = merge_report_inputs_from_db(
        request.student_id,
        request.profile or {},
        request.personality or {},
        {},
        None,
    )
    personality = merged['personality']
    profile = merged['profile']
    if not personality:
        raise HTTPException(status_code=400, detail='请先完成霍兰德职业兴趣测评')
    prompt = build_career_report_prompt(
        profile,
        personality,
        province_rule_context=merged.get('province_rule_context'),
        admission_data_context=merged.get('admission_data_context'),
    )
    try:
        content = append_ai_generated_notice(chat_completion([
            {'role': 'system', 'content': '你是专业、谨慎的高考志愿填报顾问，擅长将霍兰德职业兴趣测评与全省位次冲稳保策略结合分析。所有建议必须提示以官方信息为准。'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=1200))
        assessment_id = request.assessment_id
        if not assessment_id and request.student_id:
            latest = get_latest_assessment(request.student_id)
            assessment_id = latest.get('assessment_id') if latest else None
        if assessment_id:
            save_ai_career_report(assessment_id, content)
        return {'report': content, 'assessment_id': assessment_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post('/api/ai/student-report')
def ai_student_report(request: StudentReportRequest):
    merged = merge_report_inputs_from_db(
        request.student_id,
        request.profile or {},
        request.personality or {},
        request.preferences or {},
        request.volunteer_summary,
    )
    profile = merged['profile']
    personality = merged['personality']
    preferences = merged['preferences']
    volunteer_summary = merged['volunteer_summary']
    if not profile:
        raise HTTPException(status_code=400, detail='请先完善学生档案')
    if not personality:
        raise HTTPException(status_code=400, detail='请先完成霍兰德职业兴趣测评')
    prompt = build_student_report_prompt(
        profile,
        personality,
        preferences,
        volunteer_summary,
        province_rule_context=merged.get('province_rule_context'),
        admission_data_context=merged.get('admission_data_context'),
    )
    try:
        content = append_ai_generated_notice(chat_completion([
            {'role': 'system', 'content': '你是专业、谨慎的高考志愿填报顾问，擅长将分数位次、兴趣测评与个人需求融合为个性化报告。'},
            {'role': 'user', 'content': prompt}
        ], max_tokens=1800))
        report_id = save_student_report(
            request.student_id,
            request.user_id,
            preferences,
            content,
        )
        return {'report': content, 'report_id': report_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/ai/student-report')
def get_student_report(student_id: int):
    report = get_latest_student_report(student_id)
    if not report:
        return {'report': None}
    return {'report': report}


def _load_student_or_404(student_id: int) -> dict:
    with get_connection() as connection:
        student = row_to_dict(connection.execute(
            'SELECT * FROM students WHERE student_id = ?', [student_id]
        ).fetchone())
    if not student:
        raise HTTPException(status_code=404, detail='学生档案不存在')
    return student


def _pdf_response(pdf: bytes, filename: str) -> Response:
    # HTTP 响应头仅支持 latin-1，中文文件名用百分号编码放到自定义头
    from urllib.parse import quote

    encoded_filename = quote(filename, safe='')
    return Response(
        content=pdf,
        media_type='application/pdf',
        headers={
            'Content-Disposition': pdf_content_disposition(filename),
            'X-Pdf-Filename': encoded_filename,
        }
    )


def _resolve_student_report_content(student_id: int, report_content: str | None) -> str:
    content = (report_content or '').strip()
    if content:
        return content
    report = get_latest_student_report(student_id)
    if not report or not report.get('report_content'):
        raise HTTPException(status_code=404, detail='报告不存在，请先生成个性化报告')
    return report['report_content']


def _resolve_career_report_content(student_id: int, report_content: str | None) -> str:
    content = (report_content or '').strip()
    if content:
        return content
    assessment = get_latest_assessment(student_id)
    if not assessment or not assessment.get('ai_career_report'):
        raise HTTPException(status_code=404, detail='深度测评报告不存在，请先生成')
    return assessment['ai_career_report']


@app.get('/api/ai/student-report/pdf')
def export_student_report_pdf(student_id: int):
    student = _load_student_or_404(student_id)
    body = _resolve_student_report_content(student_id, None)
    pdf = build_text_report_pdf('智愿填报 · 个性化高考志愿填报报告', student, body)
    filename = build_student_pdf_filename(student, 'student_report')
    return _pdf_response(pdf, filename)


@app.post('/api/ai/student-report/pdf')
def export_student_report_pdf_post(request: ReportPdfExportRequest):
    student = _load_student_or_404(request.student_id)
    body = _resolve_student_report_content(request.student_id, request.report_content)
    pdf = build_text_report_pdf('智愿填报 · 个性化高考志愿填报报告', student, body)
    filename = build_student_pdf_filename(student, 'student_report')
    return _pdf_response(pdf, filename)


@app.get('/api/ai/career-report/pdf')
def export_career_report_pdf(student_id: int):
    student = _load_student_or_404(student_id)
    body = _resolve_career_report_content(student_id, None)
    pdf = build_text_report_pdf('智愿填报 · 霍兰德职业兴趣深度报告', student, body)
    filename = build_student_pdf_filename(student, 'career_report')
    return _pdf_response(pdf, filename)


@app.post('/api/ai/career-report/pdf')
def export_career_report_pdf_post(request: ReportPdfExportRequest):
    student = _load_student_or_404(request.student_id)
    body = _resolve_career_report_content(request.student_id, request.report_content)
    pdf = build_text_report_pdf('智愿填报 · 霍兰德职业兴趣深度报告', student, body)
    filename = build_student_pdf_filename(student, 'career_report')
    return _pdf_response(pdf, filename)


@app.post('/api/risk-inspect')
def risk_inspect(request: RiskInspectRequest):
    return inspect_plan_risk(request.items)


@app.post('/api/drafts')
def create_draft(request: DraftCreateRequest):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            '''
            INSERT INTO volunteer_drafts (student_id, draft_name, province, year, batch, score, rank, risk_level, ai_explain)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            [request.student_id, request.draft_name, request.province, request.year, request.batch, request.score, request.rank, request.risk_level, request.ai_explain]
        )
        draft_id = cursor.lastrowid
        for item in request.items:
            cursor.execute(
                '''
                INSERT INTO volunteer_draft_items (
                  draft_id, sort_order, gradient_type, school_id, school_name, school_code,
                  major_id, major_name, major_code, city, school_type, tuition, duration,
                  is_adjustable, risk_level, risk_reason, admission_score_2025, admission_rank_2025
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    draft_id, item.sort_order, item.gradient_type, item.school_id, item.school_name, item.school_code,
                    item.major_id, item.major_name, item.major_code, item.city, item.school_type, item.tuition,
                    item.duration, 1 if item.is_adjustable else 0, item.risk_level, item.risk_reason,
                    getattr(item, 'admission_score_2025', None), getattr(item, 'admission_rank_2025', None),
                ]
            )
        connection.commit()
    return {'draft_id': draft_id, 'message': '保存成功'}



@app.put('/api/drafts/{draft_id}')
def update_draft(draft_id: int, request: DraftUpdateRequest):
    with get_connection() as connection:
        existed = row_to_dict(connection.execute('SELECT draft_id FROM volunteer_drafts WHERE draft_id = ?', [draft_id]).fetchone())
        if not existed:
            raise HTTPException(status_code=404, detail='草稿不存在')
        connection.execute(
            '''
            UPDATE volunteer_drafts SET draft_name = ?, province = ?, year = ?, batch = ?, score = ?, rank = ?,
              risk_level = ?, ai_explain = ?, updated_at = CURRENT_TIMESTAMP
            WHERE draft_id = ? AND student_id = ?
            ''',
            [request.draft_name, request.province, request.year, request.batch, request.score, request.rank, request.risk_level, request.ai_explain, draft_id, request.student_id]
        )
        connection.execute('DELETE FROM volunteer_draft_items WHERE draft_id = ?', [draft_id])
        for item in request.items:
            connection.execute(
                '''
                INSERT INTO volunteer_draft_items (
                  draft_id, sort_order, gradient_type, school_id, school_name, school_code,
                  major_id, major_name, major_code, city, school_type, tuition, duration,
                  is_adjustable, risk_level, risk_reason, admission_score_2025, admission_rank_2025
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    draft_id, item.sort_order, item.gradient_type, item.school_id, item.school_name, item.school_code,
                    item.major_id, item.major_name, item.major_code, item.city, item.school_type, item.tuition,
                    item.duration, 1 if item.is_adjustable else 0, item.risk_level, item.risk_reason,
                    getattr(item, 'admission_score_2025', None), getattr(item, 'admission_rank_2025', None),
                ]
            )
        connection.commit()
    return {'draft_id': draft_id, 'message': '更新成功'}


@app.get('/api/drafts/{draft_id}/pdf')
def export_draft_pdf(draft_id: int, student_id: int):
    with get_connection() as connection:
        draft = row_to_dict(connection.execute(
            'SELECT * FROM volunteer_drafts WHERE draft_id = ? AND student_id = ?',
            [draft_id, student_id]
        ).fetchone())
        if not draft:
            raise HTTPException(status_code=404, detail='草稿不存在')
        student = row_to_dict(connection.execute('SELECT * FROM students WHERE student_id = ?', [student_id]).fetchone())
        items = rows_to_dicts(connection.execute(
            'SELECT * FROM volunteer_draft_items WHERE draft_id = ? ORDER BY sort_order ASC',
            [draft_id]
        ).fetchall())
    items = attach_admission_year_stats(items, draft.get('province') or '', draft.get('batch') or '')
    pdf = build_draft_pdf(draft, student or {}, items)
    filename = build_student_pdf_filename(student or {}, 'volunteer_draft')
    return _pdf_response(pdf, filename)


@app.delete('/api/drafts/{draft_id}')
def delete_draft(draft_id: int, student_id: int):
    with get_connection() as connection:
        existed = row_to_dict(connection.execute(
            'SELECT draft_id FROM volunteer_drafts WHERE draft_id = ? AND student_id = ?',
            [draft_id, student_id]
        ).fetchone())
        if not existed:
            raise HTTPException(status_code=404, detail='草稿不存在')
        connection.execute('DELETE FROM volunteer_drafts WHERE draft_id = ? AND student_id = ?', [draft_id, student_id])
        connection.commit()
    return {'draft_id': draft_id, 'message': '删除成功'}


@app.get('/api/drafts')
def list_drafts(student_id: int):
    with get_connection() as connection:
        drafts = rows_to_dicts(connection.execute(
            'SELECT * FROM volunteer_drafts WHERE student_id = ? ORDER BY created_at DESC',
            [student_id]
        ).fetchall())
        for draft in drafts:
            items = rows_to_dicts(connection.execute(
                'SELECT * FROM volunteer_draft_items WHERE draft_id = ? ORDER BY sort_order ASC',
                [draft['draft_id']]
            ).fetchall())
            draft['items'] = items
    return {'list': drafts}


@app.post('/api/import/admissions')
async def import_admissions(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows = parse_import_file(file.filename or 'upload', content)
        result = import_admission_rows(file.filename or 'upload', rows)
        return {'message': '导入完成', **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get('/api/import/logs')
def list_import_logs(limit: int = 50, offset: int = 0):
    with get_connection() as connection:
        rows = connection.execute(
            'SELECT * FROM import_logs ORDER BY created_at DESC LIMIT ? OFFSET ?',
            [limit, offset]
        ).fetchall()
    return {'list': rows_to_dicts(rows)}

