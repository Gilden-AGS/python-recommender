function openProfileModal() {
  const modal = document.getElementById("profile-modal");
  if (modal) modal.classList.remove("hidden");
  calculateBMIFromProfile();
}

function closeProfileModal(event) {
  if (event) event.preventDefault();
  const modal = document.getElementById("profile-modal");
  if (modal) modal.classList.add("hidden");
}

function calculateBMIFromProfile() {
  const w = document.getElementById("weight-input");
  const h = document.getElementById("height-input");
  const bmiEl = document.getElementById("bmi-display");
  const catEl = document.getElementById("bmi-category-display");

  if (!w || !h || !bmiEl || !catEl) return { bmi: null, category: "" };

  const weight = parseFloat(w.value);
  const height = parseFloat(h.value);

  if (!weight || !height) {
    bmiEl.textContent = "—";
    catEl.classList.add("hidden");
    return { bmi: null, category: "" };
  }

  const bmi = weight / (height * height);
  let category = "";
  if (bmi < 18.5) category = "Underweight";
  else if (bmi < 25) category = "Normal weight";
  else if (bmi < 30) category = "Overweight";
  else category = "Obese";

  const bmiText = bmi.toFixed(2);
  bmiEl.textContent = bmiText;
  catEl.textContent = category;
  catEl.classList.remove("hidden");
  return { bmi: bmiText, category };
}

function saveProfileToPills() {
  const age = document.getElementById("age-input");
  const activity = document.getElementById("activity-input");
  const diet = document.getElementById("diet-input");

  const pillAge = document.getElementById("pill-age");
  const pillBmi = document.getElementById("pill-bmi");
  const pillActivity = document.getElementById("pill-activity");
  const pillDiet = document.getElementById("pill-diet");

  if (pillAge && age) pillAge.textContent = age.value || "—";
  const { bmi } = calculateBMIFromProfile();
  if (pillBmi) pillBmi.textContent = bmi || "—";
  if (pillActivity && activity) pillActivity.textContent = activity.value || "—";
  if (pillDiet && diet) pillDiet.textContent = diet.value || "—";

  // Hidden fields for /recommend form (if present)
  const hiddenBmi = document.getElementById("bmi-hidden");
  const hiddenCat = document.getElementById("bmi-category-hidden");
  if (hiddenBmi && hiddenCat) {
    const { bmi: bmi2, category } = calculateBMIFromProfile();
    hiddenBmi.value = bmi2 || "";
    hiddenCat.value = category || "";
  }
}

function attachDashboardContext(e) {
  // When user clicks "Get Recommendations", copy checked conditions into this form.
  const form = e && e.target ? e.target : null;
  const isForm = form && form.tagName && form.tagName.toLowerCase() === "form";
  const pillBmi = document.getElementById("pill-bmi");
  const pillActivity = document.getElementById("pill-activity");
  const pillDiet = document.getElementById("pill-diet");

  const bmiHidden = document.getElementById("bmi-hidden");
  const catHidden = document.getElementById("bmi-category-hidden");
  const activityHidden = document.getElementById("activity-hidden");
  const dietHidden = document.getElementById("diet-hidden");

  if (activityHidden && pillActivity) activityHidden.value = pillActivity.textContent === "—" ? "" : pillActivity.textContent;
  if (dietHidden && pillDiet) dietHidden.value = pillDiet.textContent === "—" ? "" : pillDiet.textContent;

  // BMI: keep existing hidden values if user already saved profile; otherwise compute from modal inputs.
  if (bmiHidden) {
    if (!bmiHidden.value) {
      const computed = calculateBMIFromProfile();
      bmiHidden.value = computed.bmi || (pillBmi ? (pillBmi.textContent === "—" ? "" : pillBmi.textContent) : "");
      if (catHidden) catHidden.value = computed.category || "";
    }
  }

  if (isForm) {
    // Remove old generated hidden inputs to prevent duplicates on double-click.
    const old = form.querySelectorAll('input.symptom-hidden-input[name="symptoms"]');
    old.forEach((el) => el.remove());

    const checked = document.querySelectorAll('input[name="symptoms"]:checked');
    checked.forEach((chk) => {
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = "symptoms";
      hidden.value = chk.value;
      hidden.className = "symptom-hidden-input";
      form.appendChild(hidden);
    });
  }

  return true;
}

function scrollToRecommendations(e) {
  e.preventDefault();
  const el = document.getElementById("recommendations");
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

