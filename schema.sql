-- MySQL schema for Nutrition & Diet Recommendation System
-- Run in phpMyAdmin (SQL tab) while MySQL is running in XAMPP.

CREATE DATABASE IF NOT EXISTS nutrition_expert
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE nutrition_expert;

-- Users and auth
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NULL,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('user', 'admin') DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User health profile (for dashboard cards + personalization)
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id INT PRIMARY KEY,
  age INT NULL,
  gender ENUM('Male','Female','Other') NULL,
  weight_kg DECIMAL(6,2) NULL,
  height_m DECIMAL(4,2) NULL,
  bmi DECIMAL(5,2) NULL,
  activity_level VARCHAR(50) NULL,
  diet_preference VARCHAR(50) NULL,
  allergies_notes TEXT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Conditions/symptoms user can select
CREATE TABLE IF NOT EXISTS symptoms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT
);

-- Recommendation categories (diagnoses/plans)
CREATE TABLE IF NOT EXISTS diagnoses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  general_advice TEXT
);

-- Ghanaian foods database
CREATE TABLE IF NOT EXISTS foods (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  local_name VARCHAR(255),
  category VARCHAR(100),
  description TEXT
);

-- Link diagnoses to foods with a note
CREATE TABLE IF NOT EXISTS diagnosis_foods (
  id INT AUTO_INCREMENT PRIMARY KEY,
  diagnosis_id INT NOT NULL,
  food_id INT NOT NULL,
  note TEXT,
  FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
  FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE,
  UNIQUE KEY uniq_diag_food (diagnosis_id, food_id)
);

-- Rules: symptom -> diagnosis (weighted)
CREATE TABLE IF NOT EXISTS rules (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symptom_id INT NOT NULL,
  diagnosis_id INT NOT NULL,
  weight INT DEFAULT 1,
  FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE,
  FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE,
  UNIQUE KEY uniq_rule (symptom_id, diagnosis_id)
);

-- User selected conditions (to render chips + save profile state)
CREATE TABLE IF NOT EXISTS user_conditions (
  user_id INT NOT NULL,
  symptom_id INT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, symptom_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE
);

-- A saved "recommendation run" (timeline/history)
CREATE TABLE IF NOT EXISTS recommendation_runs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  bmi DECIMAL(5,2) NULL,
  bmi_category VARCHAR(30) NULL,
  diet_preference VARCHAR(50) NULL,
  activity_level VARCHAR(50) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Store which diagnoses were recommended in a run
CREATE TABLE IF NOT EXISTS recommendation_run_diagnoses (
  run_id INT NOT NULL,
  diagnosis_id INT NOT NULL,
  score INT NOT NULL,
  PRIMARY KEY (run_id, diagnosis_id),
  FOREIGN KEY (run_id) REFERENCES recommendation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (diagnosis_id) REFERENCES diagnoses(id) ON DELETE CASCADE
);

-- Nutrition experts (for consultation requests)
CREATE TABLE IF NOT EXISTS experts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) UNIQUE NOT NULL,
  specialty VARCHAR(120),
  contact_email VARCHAR(255),
  contact_phone VARCHAR(50),
  contact_whatsapp VARCHAR(50),
  contact_linkedin VARCHAR(255),
  contact_facebook VARCHAR(255),
  contact_instagram VARCHAR(255),
  bio TEXT
);

-- User consultation requests sent to experts
CREATE TABLE IF NOT EXISTS consultation_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  expert_id INT NOT NULL,
  user_message TEXT NOT NULL,
  status ENUM('pending','accepted','rejected','completed') DEFAULT 'pending',
  admin_response TEXT NULL,
  expert_response TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE
);

-- Expert login accounts
CREATE TABLE IF NOT EXISTS expert_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  expert_id INT NOT NULL UNIQUE,
  login_email VARCHAR(255) UNIQUE NULL,
  login_username VARCHAR(50) UNIQUE NULL,
  password_hash VARCHAR(255) NOT NULL,
  can_manage_kb TINYINT(1) NOT NULL DEFAULT 0,
  linked_user_id INT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE,
  FOREIGN KEY (linked_user_id) REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE KEY uniq_expert_users_linked_user (linked_user_id)
);

CREATE TABLE IF NOT EXISTS common_allergens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS user_allergens (
  user_id INT NOT NULL,
  allergen_id INT NOT NULL,
  PRIMARY KEY (user_id, allergen_id),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (allergen_id) REFERENCES common_allergens(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS expert_activity_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  expert_id INT NOT NULL,
  action VARCHAR(120) NOT NULL,
  detail TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  admin_user_id INT NOT NULL,
  action VARCHAR(120) NOT NULL,
  detail TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE CASCADE
);

