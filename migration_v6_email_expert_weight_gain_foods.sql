-- Migration v6:
-- 1) Add email to users (for registration/login)
-- 2) Add expert_response + expert_users (expert dashboard)
-- 3) Add expert contact link columns (optional)
-- 4) Add underweight symptom, weight-gain plan, foods, rules, and diagnosis_foods mappings
--
-- Run in phpMyAdmin (SQL tab) for database `nutrition_expert`.
-- On hosted MySQL: select your database first; comment out USE if your host forbids it.

USE nutrition_expert;

SET @db := 'nutrition_expert';

-- ---------------------------------------------------------------------------
-- USERS: add email column
-- ---------------------------------------------------------------------------
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='users' AND column_name='email'
);
SET @sql := IF(@exists=0, 'ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- EXPERTS: add social/contact columns (if missing)
-- ---------------------------------------------------------------------------
SET @col := 'contact_whatsapp';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='experts' AND column_name=@col
);
SET @sql := IF(@exists=0, 'ALTER TABLE experts ADD COLUMN contact_whatsapp VARCHAR(50) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col := 'contact_linkedin';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='experts' AND column_name=@col
);
SET @sql := IF(@exists=0, 'ALTER TABLE experts ADD COLUMN contact_linkedin VARCHAR(255) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col := 'contact_facebook';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='experts' AND column_name=@col
);
SET @sql := IF(@exists=0, 'ALTER TABLE experts ADD COLUMN contact_facebook VARCHAR(255) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col := 'contact_instagram';
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='experts' AND column_name=@col
);
SET @sql := IF(@exists=0, 'ALTER TABLE experts ADD COLUMN contact_instagram VARCHAR(255) NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- CONSULTATION_REQUESTS: add expert_response
-- ---------------------------------------------------------------------------
SET @exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema=@db AND table_name='consultation_requests' AND column_name='expert_response'
);
SET @sql := IF(@exists=0, 'ALTER TABLE consultation_requests ADD COLUMN expert_response TEXT NULL', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ---------------------------------------------------------------------------
-- EXPERT_USERS table (expert login) — minimal columns; v8+ migrations add KB flags
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS expert_users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  expert_id INT NOT NULL UNIQUE,
  login_email VARCHAR(255) UNIQUE NULL,
  login_username VARCHAR(50) UNIQUE NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (expert_id) REFERENCES experts(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- Weight gain path: symptom, plan, foods, rule, meal links
-- ---------------------------------------------------------------------------
INSERT INTO symptoms (code, name, description) VALUES
('UWT', 'Underweight', 'Low body weight for age/height')
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description);

INSERT INTO diagnoses (code, name, description, general_advice) VALUES
(
  'WEIGHT_GAIN_DIET',
  'Healthy weight gain plan',
  'Nutrient-dense meals to increase body weight safely.',
  'Increase calories gradually with balanced meals; add healthy fats and proteins (eggs, beans, groundnuts); include fruits/complex carbs; avoid junk/over-sugary foods.'
)
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), general_advice=VALUES(general_advice);

INSERT INTO foods (name, local_name, category, description) VALUES
('Oats', NULL, 'Carbohydrate', 'Soluble fiber; supports blood sugar and cholesterol management.'),
('Bananas', 'Kwadu', 'Fruit', 'Energy and potassium; choose portion sizes for blood sugar control.'),
('Sweet potatoes', NULL, 'Carbohydrate', 'Complex carbs; prefer boiled/steamed portions.'),
('Groundnuts (peanuts)', 'Nkatiɛ', 'Protein', 'Healthy fats and protein; portion carefully.'),
('Peanut butter', NULL, 'Protein', 'Concentrated energy; prefer unsweetened options when possible.'),
('Eggs', NULL, 'Protein', 'Complete protein; supports muscle gain with balanced meals.'),
('Whole milk', NULL, 'Dairy', 'Energy and protein; choose suitable options if you have restrictions.'),
('Avocado', NULL, 'Healthy fat', 'Monounsaturated fats; supports nutrient-dense meals.'),
('Rice porridge', NULL, 'Mixed', 'Comfort meal; balance with protein and vegetables.')
ON DUPLICATE KEY UPDATE local_name=VALUES(local_name), category=VALUES(category), description=VALUES(description);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3
FROM symptoms s, diagnoses d
WHERE s.code='UWT' AND d.code='WEIGHT_GAIN_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Healthy weight gain support'
FROM diagnoses d, foods f
WHERE d.code='WEIGHT_GAIN_DIET'
  AND f.name IN (
    'Rice porridge',
    'Oats',
    'Bananas',
    'Sweet potatoes',
    'Groundnuts (peanuts)',
    'Peanut butter',
    'Eggs',
    'Whole milk',
    'Avocado'
  )
ON DUPLICATE KEY UPDATE note=VALUES(note);
