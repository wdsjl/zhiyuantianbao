PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO users (user_id, openid, unionid, phone, role, name, avatar) VALUES
(1, 'demo_student_openid', NULL, '13800000000', 'student', '测试学生', NULL);

INSERT OR IGNORE INTO students (student_id, user_id, name, province, city, school_name, grade, class_name, exam_year, exam_type, subject_combination, score, rank, target_batch) VALUES
(1, 1, '测试学生', '浙江', '杭州', '示例中学', '高三', '1班', 2025, '普通类', '物理', 615, 32000, '普通类一段');

INSERT OR IGNORE INTO schools (school_code, school_name, province, city, school_type, education_level, is_985, is_211, is_double_first_class, is_public, authority, website) VALUES
('10251', '华东理工大学', '上海', '上海', '理工类', '本科', 0, 1, 1, 1, '教育部', 'https://www.ecust.edu.cn'),
('10293', '南京邮电大学', '江苏', '南京', '理工类', '本科', 0, 0, 1, 1, '江苏省', 'https://www.njupt.edu.cn'),
('10337', '浙江工业大学', '浙江', '杭州', '综合类', '本科', 0, 0, 0, 1, '浙江省', 'https://www.zjut.edu.cn'),
('10617', '重庆邮电大学', '重庆', '重庆', '理工类', '本科', 0, 0, 0, 1, '重庆市', 'https://www.cqupt.edu.cn'),
('13903', '成都锦城学院', '四川', '成都', '综合类', '本科', 0, 0, 0, 0, '四川省教育厅', 'https://www.cdjcc.edu.cn'),
('10834', '武汉职业技术学院', '湖北', '武汉', '综合类', '专科', 0, 0, 0, 1, '湖北省', 'https://www.wtc.edu.cn');

INSERT OR IGNORE INTO majors (major_code, major_name, major_category, major_type, degree_type, duration) VALUES
('080901', '计算机科学与技术', '工学', '计算机类', '本科', '4年'),
('080703', '通信工程', '工学', '电子信息类', '本科', '4年'),
('080717T', '人工智能', '工学', '电子信息类', '本科', '4年'),
('080801', '自动化', '工学', '自动化类', '本科', '4年'),
('080902', '软件工程', '工学', '计算机类', '本科', '4年'),
('510203', '软件技术', '电子与信息大类', '计算机类', '专科', '3年');

INSERT OR IGNORE INTO enrollment_plans (year, province, batch, school_id, school_code, major_id, major_code, major_name, subject_requirement, enrollment_count, tuition, duration, campus, special_notes)
SELECT 2025, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, m.major_name, '物理', 6, 6000, m.duration, '主校区', '示例招生计划'
FROM schools s, majors m
WHERE s.school_code = '10293' AND m.major_code = '080703';

INSERT OR IGNORE INTO enrollment_plans (year, province, batch, school_id, school_code, major_id, major_code, major_name, subject_requirement, enrollment_count, tuition, duration, campus, special_notes)
SELECT 2025, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, m.major_name, '物理', 8, 6000, m.duration, '主校区', '示例招生计划'
FROM schools s, majors m
WHERE s.school_code = '10337' AND m.major_code = '080901';

INSERT OR IGNORE INTO enrollment_plans (year, province, batch, school_id, school_code, major_id, major_code, major_name, subject_requirement, enrollment_count, tuition, duration, campus, special_notes)
SELECT 2025, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, m.major_name, '物理', 5, 5600, m.duration, '主校区', '示例招生计划'
FROM schools s, majors m
WHERE s.school_code = '10617' AND m.major_code = '080902';

INSERT OR IGNORE INTO admission_records (year, province, batch, school_id, school_code, major_id, major_code, min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count)
SELECT 2024, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, 622, 26000, 628, 23500, 636, 21000, 6
FROM schools s, majors m
WHERE s.school_code = '10293' AND m.major_code = '080703';

INSERT OR IGNORE INTO admission_records (year, province, batch, school_id, school_code, major_id, major_code, min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count)
SELECT 2024, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, 613, 33000, 618, 30500, 626, 26800, 8
FROM schools s, majors m
WHERE s.school_code = '10337' AND m.major_code = '080901';

INSERT OR IGNORE INTO admission_records (year, province, batch, school_id, school_code, major_id, major_code, min_score, min_rank, avg_score, avg_rank, max_score, max_rank, enrollment_count)
SELECT 2024, '浙江', '普通类一段', s.school_id, s.school_code, m.major_id, m.major_code, 601, 43000, 607, 39500, 615, 32000, 5
FROM schools s, majors m
WHERE s.school_code = '10617' AND m.major_code = '080902';

-- 各省志愿规则由 server/province_rules_service.py 在启动时自动同步（2025版）

INSERT OR IGNORE INTO import_logs (import_type, file_name, total_count, success_count, fail_count, error_message) VALUES
('seed', 'seed.sql', 14, 14, 0, NULL);
