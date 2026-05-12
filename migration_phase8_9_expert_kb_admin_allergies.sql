-- Phase 8/9: expert knowledge-base flags, user allergies, expert activity log, admin audit, rule edits support.
-- Run in phpMyAdmin for database `nutrition_expert` (after migration_v6 if applicable).

SET @db := 'nutrition_expert';

-- expert_users: KB management + optional link to site user (for granting admin)
SET @col := 'can_manage_kb';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='expert_users' AND column_name=@col
);
SET @sql := IF(@exists=0,
  'ALTER TABLE expert_users ADD COLUMN can_manage_kb TINYINT(1) NOT NULL DEFAULT 0',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col := 'linked_user_id';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='expert_users' AND column_name=@col
);
SET @sql := IF(@exists=0,
  'ALTER TABLE expert_users ADD COLUMN linked_user_id INT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- FK for linked_user_id (ignore error if duplicate)
SET @fk := (
  SELECT COUNT(*) FROM information_schema.table_constraints
  WHERE table_schema=@db AND table_name='expert_users'
    AND constraint_name='fk_expert_users_linked_user'
);
SET @sql := IF(@fk=0,
  'ALTER TABLE expert_users ADD CONSTRAINT fk_expert_users_linked_user FOREIGN KEY (linked_user_id) REFERENCES users(id) ON DELETE SET NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema=@db AND table_name='expert_users' AND index_name='uniq_expert_users_linked_user'
);
SET @sql := IF(@idx=0,
  'CREATE UNIQUE INDEX uniq_expert_users_linked_user ON expert_users (linked_user_id)',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- User profile: free-text allergies
SET @col := 'allergies_notes';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='user_profiles' AND column_name=@col
);
SET @sql := IF(@exists=0,
  'ALTER TABLE user_profiles ADD COLUMN allergies_notes TEXT NULL',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

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

INSERT IGNORE INTO common_allergens (name) VALUES
  ('Peanuts'),
  ('Tree nuts'),
  ('Milk / dairy'),
  ('Eggs'),
  ('Fish'),
  ('Shellfish'),
  ('Wheat / gluten'),
  ('Soy'),
  ('Sesame');

CREATE TABLE IF NOT EXISTS expert_activity_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  expert_id INT NOT NULL,
  action VARCHAR(120) NOT NULL,
  detail TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE,
  INDEX idx_expert_activity_expert (expert_id),
  INDEX idx_expert_activity_created (created_at)
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  admin_user_id INT NOT NULL,
  action VARCHAR(120) NOT NULL,
  detail TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_admin_audit_created (created_at)
);
