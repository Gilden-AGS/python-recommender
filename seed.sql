USE nutrition_expert;

INSERT INTO symptoms (code, name, description) VALUES
('DM2', 'Diabetes', 'Type 2 diabetes / high blood sugar'),
('HBP', 'Hypertension', 'High blood pressure'),
('OBESE', 'Obesity', 'High body weight relative to height'),
('HCHOL', 'High Cholesterol', 'High LDL cholesterol'),
('UWT', 'Underweight', 'Low body weight for age/height'),
('ULCER', 'Ulcer', 'Gastric/peptic ulcer symptoms requiring non-irritating meal choices'),
('THY', 'Thyroid Disorder', 'Thyroid condition'),
('KD', 'Kidney Disease', 'Reduced kidney function'),
('HD', 'Heart Disease', 'Cardiovascular disease')
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description);

INSERT INTO diagnoses (code, name, description, general_advice) VALUES
('DIABETIC_DIET', 'Diabetic-friendly meal plan',
 'Low glycemic index meal pattern.',
 'Choose whole grains in moderate portions, beans, vegetables; avoid sweet drinks and refined carbs.'),
('DASH_DIET', 'Hypertension (DASH) plan',
 'Blood-pressure friendly diet pattern.',
 'Reduce salt, avoid heavily processed foods, add fruits/vegetables, low-fat protein sources.'),
('WEIGHT_LOSS_DIET', 'Weight management plan',
 'Calorie deficit with high satiety meals.',
 'Prioritize protein and fiber; reduce fried foods and sugary drinks; keep portions consistent.'),
('CHOLESTEROL_PLAN', 'Cholesterol-lowering plan',
 'Focus on soluble fiber and healthy fats.',
 'Oats, beans, nuts (if no allergy), fish; reduce trans fats and high saturated fat meals.'),
('WEIGHT_GAIN_DIET', 'Healthy weight gain plan',
 'Nutrient-dense meals to increase body weight safely.',
 'Increase calories gradually with balanced meals; add healthy fats and proteins (eggs, beans, groundnuts); include fruits/complex carbs; avoid junk/over-sugary foods.'),
('ULCER_FRIENDLY_PLAN', 'Ulcer-friendly meal plan',
 'Gentle meal pattern for ulcer discomfort and gastric irritation.',
 'Prefer soft, non-spicy, low-acid meals; avoid excessive chili, very oily/fried foods, alcohol, and late-night heavy meals.')
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), general_advice=VALUES(general_advice);

INSERT INTO foods (name, local_name, category, description) VALUES
('Kontomire stew', 'Kontomire', 'Vegetable', 'Leafy greens; iron and micronutrients.'),
('Beans stew (light oil)', 'Red-red (light)', 'Protein', 'Beans with minimal oil and no sugary add-ons.'),
('Grilled tilapia', 'Tilapia', 'Protein', 'Grilled fish; reduce added salt.'),
('Boiled plantain', 'Ampesi borɔdeɛ', 'Carbohydrate', 'Prefer boiled/steamed over fried.'),
('Brown rice', NULL, 'Carbohydrate', 'Whole grain option; better glycemic response than white rice.'),
('Banku + okro stew (moderate)', 'Banku ne nkruma', 'Mixed', 'Moderate portion; okro stew can be low oil.'),
('Garden egg stew', 'Ntεntεn/abedru stew', 'Vegetable', 'Vegetable stew; reduce palm oil quantity.'),
('Fresh fruit salad', NULL, 'Fruit', 'Seasonal fruits in moderate portions.'),
('Oats', NULL, 'Carbohydrate', 'Soluble fiber; supports blood sugar and cholesterol management.'),
('Bananas', NULL, 'Fruit', 'Energy and potassium; choose portion sizes for blood sugar control.'),
('Pawpaw', NULL, 'Fruit', 'Naturally sweet fruit; works as a snack in moderation.'),
('Sweet potatoes', NULL, 'Carbohydrate', 'Complex carbs; prefer boiled/steamed portions.'),
('Groundnuts (peanuts)', NULL, 'Protein', 'Healthy fats and protein; portion carefully.'),
('Peanut butter', NULL, 'Protein', 'Concentrated energy; prefer unsweetened options when possible.'),
('Eggs', NULL, 'Protein', 'Complete protein; supports muscle gain with balanced meals.'),
('Whole milk', NULL, 'Dairy', 'Energy and protein; choose suitable options if you have restrictions.'),
('Avocado', NULL, 'Healthy fat', 'Monounsaturated fats; supports nutrient-dense meals.'),
('Rice porridge', NULL, 'Mixed', 'Comfort meal; balance with protein and vegetables.'),
('Plain kenkey + light fish stew', 'Kenkey', 'Mixed', 'Mildly seasoned option; keep spices low for ulcer comfort.'),
('Mashed yam', NULL, 'Carbohydrate', 'Soft texture and gentle on the stomach when mildly prepared.'),
('Light soup (non-spicy)', NULL, 'Soup', 'Warm and easy-to-digest soup without pepper.')
ON DUPLICATE KEY UPDATE local_name=VALUES(local_name), category=VALUES(category), description=VALUES(description);

-- Rules (symptom -> plan)
INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3 FROM symptoms s, diagnoses d
WHERE s.code='DM2' AND d.code='DIABETIC_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3 FROM symptoms s, diagnoses d
WHERE s.code='HBP' AND d.code='DASH_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3 FROM symptoms s, diagnoses d
WHERE s.code='OBESE' AND d.code='WEIGHT_LOSS_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2 FROM symptoms s, diagnoses d
WHERE s.code='HCHOL' AND d.code='CHOLESTEROL_PLAN'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3 FROM symptoms s, diagnoses d
WHERE s.code='UWT' AND d.code='WEIGHT_GAIN_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 3 FROM symptoms s, diagnoses d
WHERE s.code='ULCER' AND d.code='ULCER_FRIENDLY_PLAN'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

-- Extra cross-rules to improve recommendation quality when multiple conditions are selected.
INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2 FROM symptoms s, diagnoses d
WHERE s.code='OBESE' AND d.code='DASH_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2 FROM symptoms s, diagnoses d
WHERE s.code='HBP' AND d.code='WEIGHT_LOSS_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2 FROM symptoms s, diagnoses d
WHERE s.code='DM2' AND d.code='WEIGHT_LOSS_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

INSERT INTO rules (symptom_id, diagnosis_id, weight)
SELECT s.id, d.id, 2 FROM symptoms s, diagnoses d
WHERE s.code='HCHOL' AND d.code='DASH_DIET'
ON DUPLICATE KEY UPDATE weight=VALUES(weight);

-- Link foods to plans
INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Good choice' FROM diagnoses d, foods f
WHERE d.code='DIABETIC_DIET' AND f.name IN ('Brown rice','Beans stew (light oil)','Kontomire stew','Fresh fruit salad','Oats','Pawpaw','Sweet potatoes')
ON DUPLICATE KEY UPDATE note=VALUES(note);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Suitable for blood pressure' FROM diagnoses d, foods f
WHERE d.code='DASH_DIET' AND f.name IN ('Grilled tilapia','Kontomire stew','Garden egg stew','Fresh fruit salad','Oats','Bananas','Pawpaw','Avocado')
ON DUPLICATE KEY UPDATE note=VALUES(note);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Supports weight management' FROM diagnoses d, foods f
WHERE d.code='WEIGHT_LOSS_DIET' AND f.name IN ('Boiled plantain','Kontomire stew','Grilled tilapia','Fresh fruit salad','Oats','Rice porridge')
ON DUPLICATE KEY UPDATE note=VALUES(note);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Cholesterol-supporting choice' FROM diagnoses d, foods f
WHERE d.code='CHOLESTEROL_PLAN' AND f.name IN ('Oats','Beans stew (light oil)','Grilled tilapia','Groundnuts (peanuts)','Avocado','Kontomire stew')
ON DUPLICATE KEY UPDATE note=VALUES(note);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Healthy weight gain support' FROM diagnoses d, foods f
WHERE d.code='WEIGHT_GAIN_DIET' AND f.name IN ('Rice porridge','Oats','Bananas','Sweet potatoes','Groundnuts (peanuts)','Peanut butter','Eggs','Whole milk','Avocado')
ON DUPLICATE KEY UPDATE note=VALUES(note);

INSERT INTO diagnosis_foods (diagnosis_id, food_id, note)
SELECT d.id, f.id, 'Gentle meal option for ulcer symptoms' FROM diagnoses d, foods f
WHERE d.code='ULCER_FRIENDLY_PLAN' AND f.name IN ('Rice porridge','Mashed yam','Light soup (non-spicy)','Boiled plantain','Plain kenkey + light fish stew')
ON DUPLICATE KEY UPDATE note=VALUES(note);

-- Sample nutrition experts (seed for consultation feature)
INSERT INTO experts (name, specialty, contact_email, contact_phone, contact_whatsapp, contact_linkedin, contact_facebook, contact_instagram, bio) VALUES
('Ama Mensah', 'Nutritionist', 'ama.mensah@example.com', '+233000000001', '+233000000001', 'https://linkedin.com/in/ama-mensah', 'https://facebook.com/ama-mensah', 'https://instagram.com/ama-mensah', 'Evidence-based nutrition guidance with Ghana-friendly meal planning.'),
('Kwame Asare', 'Dietitian', 'kwame.asare@example.com', '+233000000002', '+233000000002', 'https://linkedin.com/in/kwame-asare', 'https://facebook.com/kwame-asare', 'https://instagram.com/kwame-asare', 'Diet plans for diabetes, hypertension and weight management.'),
('Esi Owusu', 'Health Coach', 'esi.owusu@example.com', '+233000000003', '+233000000003', 'https://linkedin.com/in/esi-owusu', 'https://facebook.com/esi-owusu', 'https://instagram.com/esi-owusu', 'Lifestyle support, meal routines, and practical local food advice.')
ON DUPLICATE KEY UPDATE
  specialty=VALUES(specialty),
  contact_email=VALUES(contact_email),
  contact_phone=VALUES(contact_phone),
  contact_whatsapp=VALUES(contact_whatsapp),
  contact_linkedin=VALUES(contact_linkedin),
  contact_facebook=VALUES(contact_facebook),
  contact_instagram=VALUES(contact_instagram),
  bio=VALUES(bio);

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

