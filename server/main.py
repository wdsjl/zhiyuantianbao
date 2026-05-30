from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from db import get_connection, rows_to_dicts, row_to_dict
from schemas import RecommendRequest, RiskInspectRequest, DraftCreateRequest, ProfileSaveRequest, LoginRequest, ParentBindRequest, DraftUpdateRequest, PlanExplainRequest, OpenRequestCreate
from services import get_gradient_type, get_risk_level, get_risk_reason, inspect_plan_risk
from import_service import parse_import_file, import_admission_rows
from admin_views import admin_home, admin_import, admin_logs, admin_schools, admin_majors, admin_admissions, admin_students, admin_data_sources, admin_llm_settings, admin_membership_plans, admin_membership_users, admin_membership_usage, admin_payments
from llm_settings_service import save_llm_settings, get_llm_settings, test_llm_connection, chat_completion
from data_fetch_service import create_source, fetch_source, list_sources, list_tasks, list_records
from auth_service import login_or_create_user
from pdf_service import build_draft_pdf, escape_pdf_name
from membership_service import ensure_membership_tables, save_plan, save_plan_permission, grant_membership, get_user_entitlements, list_plans, check_permission, consume_permission, reset_permission_usage, delete_permission_usage, expire_overdue_memberships
from payment_service import ensure_payment_tables, create_manual_order, create_open_request, create_order_from_request, cancel_open_request, list_user_open_requests, list_user_orders, get_support_contact, save_support_contact, export_orders_csv, export_open_requests_csv

app = FastAPI(title='智愿填报 API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def ensure_draft_ai_column() -> None:
    with get_connection() as connection:
        columns = [row['name'] for row in connection.execute('PRAGMA table_info(volunteer_drafts)').fetchall()]
        if 'ai_explain' not in columns:
            connection.execute('ALTER TABLE volunteer_drafts ADD COLUMN ai_explain TEXT')
            connection.commit()


ensure_draft_ai_column()
ensure_membership_tables()
ensure_payment_tables()
expire_overdue_memberships()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/admin')
def admin_index():
    return admin_home()


@app.get('/admin/import')
def admin_import_page():
    return admin_import()


@app.post('/admin/import')
async def admin_import_submit(file: UploadFile = File(...)):
    content = await file.read()
    try:
        rows = parse_import_file(file.filename or 'upload', content)
        result = import_admission_rows(file.filename or 'upload', rows)
        message = f"导入完成：共 {result['total_count']} 条，成功 {result['success_count']} 条，失败 {result['fail_count']} 条"
        return admin_import(message)
    except ValueError as exc:
        return admin_import(f'导入失败：{exc}')


@app.get('/admin/import/logs')
def admin_import_logs_page():
    return admin_logs()


@app.get('/admin/schools')
def admin_schools_page(keyword: str = ''):
    return admin_schools(keyword)


@app.get('/admin/majors')
def admin_majors_page(keyword: str = ''):
    return admin_majors(keyword)


@app.get('/admin/students')
def admin_students_page(keyword: str = ''):
    return admin_students(keyword)



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
    return RedirectResponse('/admin/membership/users?message=会员已开通或调整', status_code=303)




@app.get('/admin/payments')
def admin_payments_page(keyword: str = '', message: str = ''):
    return admin_payments(keyword, message)





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





@app.get('/api/membership/support-contact')
def api_membership_support_contact():
    return get_support_contact()


@app.get('/api/membership/my-status')
def api_membership_my_status(user_id: int):
    return {
        'requests': list_user_open_requests(user_id),
        'orders': list_user_orders(user_id)
    }


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
    return {'list': [plan for plan in list_plans() if plan.get('is_active')]}


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
    return get_user_entitlements(user_id)


@app.get('/admin/admissions')
def admin_admissions_page(province: str = '', batch: str = '', year: str = ''):
    return admin_admissions(province, batch, year)




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
def admin_data_sources_page(keyword: str = '', message: str = ''):
    return admin_data_sources(keyword, message)


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


@app.post('/api/auth/login')
def login(request: LoginRequest):
    try:
        return login_or_create_user(request.code, request.openid, request.phone, request.name, request.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
                raise HTTPException(status_code=409, detail='该手机号已绑定其他微信账号，不能重复注册使用')
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
    is_public: int | None = Query(default=None),
    is_double_first_class: int | None = Query(default=None),
    limit: int = 50,
    offset: int = 0
):
    sql = 'SELECT * FROM schools WHERE 1=1'
    params = []
    if keyword:
        sql += ' AND (school_name LIKE ? OR school_code LIKE ? OR city LIKE ?)'
        like = f'%{keyword}%'
        params.extend([like, like, like])
    if city:
        sql += ' AND city = ?'
        params.append(city)
    if is_public is not None:
        sql += ' AND is_public = ?'
        params.append(is_public)
    if is_double_first_class is not None:
        sql += ' AND is_double_first_class = ?'
        params.append(is_double_first_class)
    sql += ' ORDER BY is_985 DESC, is_211 DESC, is_double_first_class DESC, school_id ASC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return {'list': rows_to_dicts(rows)}


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
    limit: int = 100,
    offset: int = 0
):
    sql = '''
    SELECT ar.*, s.school_name, s.city, s.is_public, s.is_double_first_class, m.major_name, m.major_type
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    WHERE 1=1
    '''
    params = []
    if province:
        sql += ' AND ar.province = ?'
        params.append(province)
    if batch:
        sql += ' AND ar.batch = ?'
        params.append(batch)
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


@app.post('/api/recommend')
def recommend(request: RecommendRequest):
    sql = """
    SELECT ar.*, s.school_name, s.city, s.school_type, s.is_public, s.is_double_first_class,
           m.major_name, m.major_type, ep.tuition, ep.duration, ep.subject_requirement
    FROM admission_records ar
    JOIN schools s ON s.school_id = ar.school_id
    JOIN majors m ON m.major_id = ar.major_id
    LEFT JOIN enrollment_plans ep ON ep.school_id = ar.school_id
      AND ep.major_id = ar.major_id
      AND ep.province = ar.province
      AND ep.batch = ar.batch
    WHERE ar.province = ? AND ar.batch = ?
    """
    params = [request.province, request.batch]

    if request.cities:
        sql += f" AND s.city IN ({','.join(['?'] * len(request.cities))})"
        params.extend(request.cities)
    if request.school_types:
        sql += f" AND s.school_type IN ({','.join(['?'] * len(request.school_types))})"
        params.extend(request.school_types)
    if request.major_types:
        sql += f" AND m.major_type IN ({','.join(['?'] * len(request.major_types))})"
        params.extend(request.major_types)
    if request.only_public is not None:
        sql += ' AND s.is_public = ?'
        params.append(1 if request.only_public else 0)

    sql += ' ORDER BY ar.year DESC, ar.min_rank ASC'

    with get_connection() as connection:
        rows = rows_to_dicts(connection.execute(sql, params).fetchall())

    grouped = {}
    for row in rows:
        key = (row['school_id'], row['major_id'])
        grouped.setdefault(key, []).append(row)

    weighted_items = []
    year_weights = [0.5, 0.3, 0.2]
    for records in grouped.values():
        sorted_records = sorted(records, key=lambda item: item['year'], reverse=True)[:3]
        weight_sum = 0
        rank_sum = 0
        score_sum = 0
        latest = sorted_records[0]
        for index, record in enumerate(sorted_records):
            weight = year_weights[index] if index < len(year_weights) else 0
            if record.get('min_rank') is not None:
                rank_sum += record['min_rank'] * weight
                weight_sum += weight
            if record.get('min_score') is not None:
                score_sum += record['min_score'] * weight
        weighted_rank = round(rank_sum / weight_sum) if weight_sum else latest.get('min_rank')
        weighted_score = round(score_sum / weight_sum) if weight_sum else latest.get('min_score')
        weighted_items.append({**latest, 'weighted_rank': weighted_rank, 'weighted_score': weighted_score, 'years_used': [item['year'] for item in sorted_records]})

    weighted_items.sort(key=lambda item: abs((item.get('weighted_rank') or request.rank) - request.rank))

    items = []
    for index, row in enumerate(weighted_items[:40], start=1):
        gradient_type = get_gradient_type(request.rank, row.get('weighted_rank'))
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
            'city': row['city'],
            'school_type': row['school_type'],
            'tuition': row.get('tuition'),
            'duration': row.get('duration'),
            'min_score': row.get('min_score'),
            'min_rank': row.get('min_rank'),
            'weighted_score': row.get('weighted_score'),
            'weighted_rank': row.get('weighted_rank'),
            'years_used': row.get('years_used'),
            'is_adjustable': is_adjustable,
            'risk_level': risk_level,
            'risk_reason': get_risk_reason(gradient_type, is_adjustable)
        })

    return {'items': items, 'risk': inspect_plan_risk(items), 'algorithm': '近三年位次加权：最近一年50%，第二年30%，第三年20%'}


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

学生信息：
省份：{profile.get('province', '')}
批次：{profile.get('targetBatch', profile.get('batch', ''))}
选科：{profile.get('subjectCombination', '')}
分数：{profile.get('score', '')}
位次：{profile.get('rank', '')}

性格测评：
代码：{personality.get('code', '')}
主类型：{(personality.get('primaryType') or {}).get('name', '')}
推荐专业大类：{', '.join(personality.get('majorTypes') or [])}

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
        return {'explain': content}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
                  is_adjustable, risk_level, risk_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    draft_id, item.sort_order, item.gradient_type, item.school_id, item.school_name, item.school_code,
                    item.major_id, item.major_name, item.major_code, item.city, item.school_type, item.tuition,
                    item.duration, 1 if item.is_adjustable else 0, item.risk_level, item.risk_reason
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
                  is_adjustable, risk_level, risk_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                [
                    draft_id, item.sort_order, item.gradient_type, item.school_id, item.school_name, item.school_code,
                    item.major_id, item.major_name, item.major_code, item.city, item.school_type, item.tuition,
                    item.duration, 1 if item.is_adjustable else 0, item.risk_level, item.risk_reason
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
    pdf = build_draft_pdf(draft, student or {}, items)
    filename = f'{escape_pdf_name(draft.get("draft_name") or "志愿方案")}.pdf'
    return Response(
        content=pdf,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


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

