-- MySQL 8.0+ 建表脚本，用于从 SQLite 迁移到生产数据库。
-- 建议先在测试库执行，并通过导出 CSV / 数据迁移脚本导入历史数据。

CREATE DATABASE IF NOT EXISTS zhiyuan CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE zhiyuan;

CREATE TABLE IF NOT EXISTS users (
  user_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  openid VARCHAR(128) UNIQUE,
  unionid VARCHAR(128),
  phone VARCHAR(32),
  role ENUM('student', 'parent', 'teacher', 'admin') NOT NULL,
  name VARCHAR(64),
  avatar VARCHAR(512),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS students (
  student_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  name VARCHAR(64),
  province VARCHAR(32) NOT NULL,
  city VARCHAR(32),
  school_name VARCHAR(128),
  grade VARCHAR(32),
  class_name VARCHAR(64),
  exam_year INT NOT NULL,
  exam_type VARCHAR(32),
  subject_combination VARCHAR(64) NOT NULL,
  score INT NOT NULL,
  `rank` INT NOT NULL,
  target_batch VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_students_area (province, city),
  INDEX idx_students_rank (exam_year, province, target_batch, `rank`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS parent_student_binds (
  bind_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  parent_user_id BIGINT NOT NULL,
  student_user_id BIGINT NOT NULL,
  student_id BIGINT NOT NULL,
  bind_status ENUM('pending', 'active', 'disabled') NOT NULL DEFAULT 'active',
  bind_code VARCHAR(64),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_binds_parent FOREIGN KEY (parent_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_binds_student_user FOREIGN KEY (student_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_binds_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
  UNIQUE KEY uk_parent_student (parent_user_id, student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS schools (
  school_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  school_code VARCHAR(32) NOT NULL UNIQUE,
  school_name VARCHAR(128) NOT NULL,
  province VARCHAR(32),
  city VARCHAR(32),
  school_type VARCHAR(64),
  education_level VARCHAR(32),
  is_985 TINYINT NOT NULL DEFAULT 0,
  is_211 TINYINT NOT NULL DEFAULT 0,
  is_double_first_class TINYINT NOT NULL DEFAULT 0,
  is_public TINYINT NOT NULL DEFAULT 1,
  authority VARCHAR(128),
  website VARCHAR(512),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_schools_name (school_name),
  INDEX idx_schools_city (city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS majors (
  major_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  major_code VARCHAR(32) NOT NULL UNIQUE,
  major_name VARCHAR(128) NOT NULL,
  major_category VARCHAR(64),
  major_type VARCHAR(64),
  degree_type VARCHAR(64),
  duration VARCHAR(32),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_majors_name (major_name),
  INDEX idx_majors_type (major_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS enrollment_plans (
  plan_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  year INT NOT NULL,
  province VARCHAR(32) NOT NULL,
  batch VARCHAR(64) NOT NULL,
  school_id BIGINT NOT NULL,
  major_id BIGINT NOT NULL,
  plan_count INT,
  tuition INT,
  duration VARCHAR(32),
  subject_requirement VARCHAR(128),
  remark VARCHAR(512),
  CONSTRAINT fk_plans_school FOREIGN KEY (school_id) REFERENCES schools(school_id),
  CONSTRAINT fk_plans_major FOREIGN KEY (major_id) REFERENCES majors(major_id),
  INDEX idx_plans_query (year, province, batch, school_id, major_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admission_records (
  admission_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  year INT NOT NULL,
  province VARCHAR(32) NOT NULL,
  batch VARCHAR(64) NOT NULL,
  school_id BIGINT NOT NULL,
  school_code VARCHAR(32) NOT NULL,
  major_id BIGINT NOT NULL,
  major_code VARCHAR(32) NOT NULL,
  min_score INT,
  min_rank INT,
  avg_score INT,
  avg_rank INT,
  max_score INT,
  enrollment_count INT,
  source_name VARCHAR(128),
  source_url VARCHAR(512),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_admissions_school FOREIGN KEY (school_id) REFERENCES schools(school_id),
  CONSTRAINT fk_admissions_major FOREIGN KEY (major_id) REFERENCES majors(major_id),
  INDEX idx_admissions_query (province, batch, year, min_rank),
  INDEX idx_admissions_school_major (school_id, major_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS volunteer_drafts (
  draft_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  student_id BIGINT NOT NULL,
  draft_name VARCHAR(128) NOT NULL,
  province VARCHAR(32) NOT NULL,
  year INT NOT NULL,
  batch VARCHAR(64) NOT NULL,
  score INT NOT NULL,
  `rank` INT NOT NULL,
  risk_level VARCHAR(32),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_drafts_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
  INDEX idx_drafts_student (student_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS volunteer_draft_items (
  item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  draft_id BIGINT NOT NULL,
  sort_order INT NOT NULL,
  gradient_type VARCHAR(16) NOT NULL,
  school_id BIGINT NOT NULL,
  school_name VARCHAR(128) NOT NULL,
  school_code VARCHAR(32) NOT NULL,
  major_id BIGINT NOT NULL,
  major_name VARCHAR(128) NOT NULL,
  major_code VARCHAR(32) NOT NULL,
  city VARCHAR(32),
  school_type VARCHAR(64),
  tuition INT,
  duration VARCHAR(32),
  is_adjustable TINYINT NOT NULL DEFAULT 1,
  risk_level VARCHAR(32),
  risk_reason VARCHAR(512),
  CONSTRAINT fk_draft_items_draft FOREIGN KEY (draft_id) REFERENCES volunteer_drafts(draft_id) ON DELETE CASCADE,
  INDEX idx_draft_items_draft (draft_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS import_logs (
  log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  import_type VARCHAR(64) NOT NULL,
  file_name VARCHAR(255),
  total_count INT NOT NULL DEFAULT 0,
  success_count INT NOT NULL DEFAULT 0,
  fail_count INT NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
