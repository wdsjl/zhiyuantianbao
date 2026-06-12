PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  openid TEXT UNIQUE,
  unionid TEXT,
  phone TEXT,
  role TEXT NOT NULL CHECK (role IN ('student', 'parent', 'teacher', 'admin')),
  name TEXT,
  avatar TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS students (
  student_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT,
  province TEXT NOT NULL,
  city TEXT,
  school_name TEXT,
  grade TEXT,
  class_name TEXT,
  exam_year INTEGER NOT NULL,
  exam_type TEXT,
  subject_combination TEXT NOT NULL,
  score INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  target_batch TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS parent_student_binds (
  bind_id INTEGER PRIMARY KEY AUTOINCREMENT,
  parent_user_id INTEGER NOT NULL,
  student_user_id INTEGER NOT NULL,
  student_id INTEGER NOT NULL,
  bind_status TEXT NOT NULL DEFAULT 'active' CHECK (bind_status IN ('pending', 'active', 'disabled')),
  bind_code TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (parent_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (student_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schools (
  school_id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_code TEXT NOT NULL UNIQUE,
  school_name TEXT NOT NULL,
  province TEXT,
  city TEXT,
  school_type TEXT,
  education_level TEXT,
  is_985 INTEGER NOT NULL DEFAULT 0,
  is_211 INTEGER NOT NULL DEFAULT 0,
  is_double_first_class INTEGER NOT NULL DEFAULT 0,
  is_public INTEGER NOT NULL DEFAULT 1,
  authority TEXT,
  website TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS majors (
  major_id INTEGER PRIMARY KEY AUTOINCREMENT,
  major_code TEXT NOT NULL UNIQUE,
  major_name TEXT NOT NULL,
  major_category TEXT,
  major_type TEXT,
  degree_type TEXT,
  duration TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrollment_plans (
  plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
  year INTEGER NOT NULL,
  province TEXT NOT NULL,
  batch TEXT NOT NULL,
  school_id INTEGER NOT NULL,
  school_code TEXT NOT NULL,
  major_id INTEGER NOT NULL,
  major_code TEXT NOT NULL,
  major_name TEXT NOT NULL,
  subject_requirement TEXT,
  enrollment_count INTEGER,
  tuition INTEGER,
  duration TEXT,
  campus TEXT,
  special_notes TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
  FOREIGN KEY (major_id) REFERENCES majors(major_id) ON DELETE CASCADE,
  UNIQUE (year, province, batch, school_id, major_id)
);

CREATE TABLE IF NOT EXISTS admission_records (
  admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
  year INTEGER NOT NULL,
  province TEXT NOT NULL,
  batch TEXT NOT NULL,
  school_id INTEGER NOT NULL,
  school_code TEXT NOT NULL,
  major_id INTEGER NOT NULL,
  major_code TEXT NOT NULL,
  min_score INTEGER,
  min_rank INTEGER,
  avg_score INTEGER,
  avg_rank INTEGER,
  max_score INTEGER,
  max_rank INTEGER,
  enrollment_count INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
  FOREIGN KEY (major_id) REFERENCES majors(major_id) ON DELETE CASCADE,
  UNIQUE (year, province, batch, school_id, major_id)
);

CREATE TABLE IF NOT EXISTS province_rules (
  rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
  province TEXT NOT NULL,
  year INTEGER NOT NULL,
  batch TEXT NOT NULL,
  volunteer_mode TEXT NOT NULL,
  school_count INTEGER,
  major_count_per_school INTEGER,
  is_parallel_volunteer INTEGER NOT NULL DEFAULT 1,
  adjustment_supported INTEGER NOT NULL DEFAULT 1,
  score_priority_rule TEXT,
  rule_description TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (province, year, batch)
);

CREATE TABLE IF NOT EXISTS volunteer_drafts (
  draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL,
  draft_name TEXT NOT NULL,
  province TEXT NOT NULL,
  year INTEGER NOT NULL,
  batch TEXT NOT NULL,
  score INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  risk_level TEXT,
  ai_explain TEXT,
  is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS volunteer_draft_items (
  item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id INTEGER NOT NULL,
  sort_order INTEGER NOT NULL,
  gradient_type TEXT NOT NULL CHECK (gradient_type IN ('冲', '稳', '保', '垫')),
  school_id INTEGER NOT NULL,
  school_name TEXT NOT NULL,
  school_code TEXT NOT NULL,
  major_id INTEGER NOT NULL,
  major_name TEXT NOT NULL,
  major_code TEXT NOT NULL,
  city TEXT,
  school_type TEXT,
  tuition INTEGER,
  duration TEXT,
  is_adjustable INTEGER NOT NULL DEFAULT 1,
  risk_level TEXT,
  risk_reason TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (draft_id) REFERENCES volunteer_drafts(draft_id) ON DELETE CASCADE,
  FOREIGN KEY (school_id) REFERENCES schools(school_id) ON DELETE CASCADE,
  FOREIGN KEY (major_id) REFERENCES majors(major_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_logs (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  import_type TEXT NOT NULL,
  file_name TEXT,
  total_count INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_user_id ON students(user_id);
CREATE INDEX IF NOT EXISTS idx_schools_city ON schools(city);
CREATE INDEX IF NOT EXISTS idx_schools_tags ON schools(is_985, is_211, is_double_first_class, is_public);
CREATE INDEX IF NOT EXISTS idx_enrollment_query ON enrollment_plans(year, province, batch, school_id, major_id);
CREATE INDEX IF NOT EXISTS idx_admission_query ON admission_records(year, province, batch, min_rank, min_score);
CREATE INDEX IF NOT EXISTS idx_drafts_student ON volunteer_drafts(student_id, created_at);


CREATE TABLE IF NOT EXISTS data_sources (
  source_id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_id INTEGER,
  school_code TEXT,
  school_name TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT '高校官网',
  data_type TEXT NOT NULL DEFAULT '招生信息',
  year INTEGER,
  province TEXT,
  url TEXT NOT NULL,
  parser_type TEXT NOT NULL DEFAULT 'link_discovery',
  is_active INTEGER NOT NULL DEFAULT 1,
  last_fetch_at TEXT,
  last_status TEXT,
  remark TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS data_fetch_tasks (
  task_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id INTEGER NOT NULL,
  task_status TEXT NOT NULL DEFAULT 'pending',
  fetch_url TEXT NOT NULL,
  content_type TEXT,
  page_title TEXT,
  links_count INTEGER NOT NULL DEFAULT 0,
  matched_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS data_fetch_records (
  record_id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  source_id INTEGER NOT NULL,
  record_type TEXT NOT NULL,
  title TEXT,
  url TEXT NOT NULL,
  file_ext TEXT,
  matched_keyword TEXT,
  review_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (task_id) REFERENCES data_fetch_tasks(task_id) ON DELETE CASCADE,
  FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enrollment_announcements (
  announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_org TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'university',
  school_id INTEGER,
  school_code TEXT,
  school_name TEXT,
  province TEXT,
  target_province TEXT,
  year INTEGER NOT NULL DEFAULT 2026,
  title TEXT NOT NULL,
  announcement_type TEXT NOT NULL DEFAULT '招生公告',
  url TEXT NOT NULL,
  url_hash TEXT NOT NULL,
  file_url TEXT,
  file_ext TEXT,
  published_at TEXT,
  matched_keywords TEXT,
  mentions_henan INTEGER NOT NULL DEFAULT 0,
  crawl_status TEXT NOT NULL DEFAULT 'discovered',
  review_status TEXT NOT NULL DEFAULT 'pending',
  parse_status TEXT NOT NULL DEFAULT 'pending',
  parse_message TEXT,
  parsed_plan_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(url_hash)
);

CREATE TABLE IF NOT EXISTS announcement_crawl_logs (
  log_id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_name TEXT NOT NULL,
  province TEXT,
  year INTEGER NOT NULL,
  source_total INTEGER NOT NULL DEFAULT 0,
  source_processed INTEGER NOT NULL DEFAULT 0,
  discovered_count INTEGER NOT NULL DEFAULT 0,
  new_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running',
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_announcements_province_year ON enrollment_announcements(target_province, year, review_status);
CREATE INDEX IF NOT EXISTS idx_announcements_henan ON enrollment_announcements(mentions_henan, year);

CREATE TABLE IF NOT EXISTS admission_brochures (
  brochure_id INTEGER PRIMARY KEY AUTOINCREMENT,
  school_id INTEGER,
  school_code TEXT,
  school_name TEXT NOT NULL,
  year INTEGER,
  title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  file_url TEXT,
  content_text TEXT,
  admission_rule TEXT,
  adjustment_rule TEXT,
  single_subject_requirement TEXT,
  physical_requirement TEXT,
  language_requirement TEXT,
  tuition_rule TEXT,
  published_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS llm_settings (
  setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider TEXT NOT NULL DEFAULT 'openai-compatible',
  base_url TEXT,
  api_key TEXT,
  model_name TEXT,
  temperature REAL NOT NULL DEFAULT 0.7,
  is_enabled INTEGER NOT NULL DEFAULT 0,
  remark TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS membership_plans (
  plan_code TEXT PRIMARY KEY,
  plan_name TEXT NOT NULL,
  price REAL NOT NULL DEFAULT 0,
  duration_days INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  description TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS membership_permissions (
  permission_code TEXT PRIMARY KEY,
  permission_name TEXT NOT NULL,
  category TEXT,
  description TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS membership_plan_permissions (
  plan_code TEXT NOT NULL,
  permission_code TEXT NOT NULL,
  is_enabled INTEGER NOT NULL DEFAULT 0,
  limit_value INTEGER NOT NULL DEFAULT 0,
  remark TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plan_code, permission_code),
  FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE,
  FOREIGN KEY (permission_code) REFERENCES membership_permissions(permission_code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_memberships (
  user_membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  plan_code TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'expired', 'disabled')),
  starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT,
  source TEXT,
  remark TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_memberships_user ON user_memberships(user_id, status, expires_at);


CREATE TABLE IF NOT EXISTS user_permission_usage (
  usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  permission_code TEXT NOT NULL,
  plan_code TEXT NOT NULL,
  user_membership_id INTEGER,
  period_key TEXT NOT NULL,
  used_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, permission_code, period_key),
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_permission_usage_user ON user_permission_usage(user_id, permission_code, period_key);


CREATE TABLE IF NOT EXISTS payment_orders (
  order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_no TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL,
  plan_code TEXT NOT NULL,
  amount REAL NOT NULL DEFAULT 0,
  pay_method TEXT NOT NULL DEFAULT 'manual',
  pay_status TEXT NOT NULL DEFAULT 'paid' CHECK(pay_status IN ('pending', 'paid', 'refunded', 'cancelled')),
  order_type TEXT NOT NULL DEFAULT 'manual' CHECK(order_type IN ('open', 'renew', 'manual')),
  payer_name TEXT,
  payer_contact TEXT,
  paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  opened_membership_id INTEGER,
  remark TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user ON payment_orders(user_id, paid_at);


CREATE TABLE IF NOT EXISTS membership_open_requests (
  request_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  plan_code TEXT NOT NULL,
  contact_name TEXT,
  contact_phone TEXT,
  message TEXT,
  request_type TEXT NOT NULL DEFAULT 'open' CHECK(request_type IN ('open', 'renew')),
  request_status TEXT NOT NULL DEFAULT 'pending' CHECK(request_status IN ('pending', 'processed', 'cancelled')),
  created_order_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (plan_code) REFERENCES membership_plans(plan_code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_open_requests_status ON membership_open_requests(request_status, created_at);


CREATE TABLE IF NOT EXISTS app_settings (
  setting_key TEXT PRIMARY KEY,
  setting_value TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS referral_agents (
  agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  invite_code TEXT NOT NULL UNIQUE,
  display_name TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
  commission_rate REAL NOT NULL DEFAULT 10,
  total_invites INTEGER NOT NULL DEFAULT 0,
  total_paid_orders INTEGER NOT NULL DEFAULT 0,
  total_commission REAL NOT NULL DEFAULT 0,
  settled_commission REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS referral_bindings (
  binding_id INTEGER PRIMARY KEY AUTOINCREMENT,
  invitee_user_id INTEGER NOT NULL UNIQUE,
  agent_id INTEGER NOT NULL,
  invite_code TEXT NOT NULL,
  bind_source TEXT NOT NULL DEFAULT 'poster',
  bound_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  first_paid_order_id INTEGER,
  FOREIGN KEY (invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS referral_commissions (
  commission_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL UNIQUE,
  order_no TEXT NOT NULL,
  agent_id INTEGER NOT NULL,
  invitee_user_id INTEGER NOT NULL,
  order_amount REAL NOT NULL DEFAULT 0,
  commission_rate REAL NOT NULL DEFAULT 0,
  commission_amount REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'settled', 'cancelled')),
  settled_at TEXT,
  remark TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES payment_orders(order_id) ON DELETE CASCADE,
  FOREIGN KEY (agent_id) REFERENCES referral_agents(agent_id) ON DELETE CASCADE,
  FOREIGN KEY (invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
