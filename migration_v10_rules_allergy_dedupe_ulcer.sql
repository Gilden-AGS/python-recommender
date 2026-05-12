-- Migration v10:
-- 1) Add ulcer condition + ulcer-friendly plan + rule mappings
-- 2) Add extra cross-condition rules
-- 3) Add ulcer-friendly food mappings
-- 4) Remove duplicate diagnosis-food links and enforce uniqueness
--
-- Run this in phpMyAdmin for database `nutrition_expert`.

USE nutrition_expert;

-- -------------------------
-- Add condition + plan data
-- -------------------------
INSERT INTO symptoms (code, name, description)
VALUES ('ULCER', 'Ulcer', 'Gastric/peptic ulcer symptoms requiring non-irritating meal choices')
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  description = VALUES(description);

INSERT INTO diagnoses (code, name, description, general_advice)
VALUES (
  'ULCER_FRIENDLY_PLAN',
  'Ulcer-friendly meal plan',
  'Gentle meal pattern for ulcer discomfort and gastric irritation.',
  'Prefer soft, non-spicy, low-acid meals; avoid excessive chili, very oily/fried foods, alcohol, and late-night heavy meals.'
)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  description = VALUES(description),
  general_advice = VALUES(general_advice);

INSERT INTO foods (name, local_name, category, description) VALUES
('Plain kenkey + light fish stew', 'Kenkey', 'Mixed', 'Mildly seasoned option; keep spices low for ulcer comfort.'),
('Mashed yam', NULL, 'Carbohydrate', 'Soft texture and gentle on the stomach when mildly prepared.'),
('Light soup (non-spicy)', NULL, 'Soup', 'Warm and easy-to-digest soup without pepper.')
ON DUPLICATE KEY UPDATE
  local_name=VALUES(local_name),
  category=VALUES(category),
  description=VALUES(description);

-- -------------------------
-- Add/expand rules
-- -------------------------
INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3
FROM symptoms s, diagnoses d
WHERE s.code='ULCER' AND d.code='ULCER_FRIENDLY_PLAN'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2
FROM symptoms s, diagnoses d
WHERE s.code='OBESE' AND d.code='DASH_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2
FROM symptoms s, diagnoses d
WHERE s.code='HBP' AND d.code='WEIGHT_LOSS_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2
FROM symptoms s, diagnoses d
WHERE s.code='DM2' AND d.code='WEIGHT_LOSS_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2
FROM symptoms s, diagnoses d
WHERE s.code='HCHOL' AND d.code='DASH_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Gentle meal option for ulcer symptoms'
FROM diagnoses d, foods f
WHERE d.code='ULCER_FRIENDLY_PLAN'
  AND f.name IN ('Rice porridge','Mashed yam','Light soup (non-spicy)','Boiled plantain','Plain kenkey + light fish stew')
ON DUPLICATE KEY UPDATE note=VALUES(note);

-- ----------------------------------------------------------
-- Remove duplicate diagnosis-food pairs in legacy databases
-- ----------------------------------------------------------
CREATE TEMPORARY TABLE tmp_diag_food_min AS
SELECT diagnosis_id, food_id, MIN(id) AS keep_id
FROM diagnosis_foods
GROUP BY diagnosis_id, food_id;

DELETE df
FROM diagnosis_foods df
LEFT JOIN tmp_diag_food_min t
  ON t.keep_id = df.id
WHERE t.keep_id IS NULL;

DROP TEMPORARY TABLE tmp_diag_food_min;

-- Ensure uniqueness exists (older DBs may miss this key)
SET @db := 'nutrition_expert';
SET @uniq_exists := (
  SELECT COUNT(*)
  FROM information_schema.statistics
  WHERE table_schema=@db
    AND table_name='diagnosis_foods'
    AND index_name='uniq_diag_food'
);
SET @sql := IF(
  @uniq_exists=0,
  'ALTER TABLE diagnosis_foods ADD UNIQUE KEY uniq_diag_food (diagnosis_id, food_id)',
  'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
