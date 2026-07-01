const API_BASE = "";

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach(l => {
    l.classList.toggle("active", l.dataset.page === page);
  });
  document.getElementById(`page-${page}`).classList.add("active");
  if (page === "home" && !window._homeLoaded) { loadHome(); window._homeLoaded = true; }
}

// ── Company colors (stripe + pill) ─────────────────────────────────────────
const COMPANY_COLORS = [
  "#1a56db","#10b981","#f59e0b","#ef4444","#8b5cf6",
  "#0ea5e9","#ec4899","#14b8a6","#f97316","#6366f1",
  "#84cc16","#06b6d4","#a855f7","#e11d48","#059669",
  "#d97706","#2563eb","#dc2626","#7c3aed","#0891b2","#16a34a"
];
function companyColor(name) {
  let h = 0; for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff;
  return COMPANY_COLORS[h % COMPANY_COLORS.length];
}

// ── Stars ───────────────────────────────────────────────────────────────────
function stars(rating) {
  const full = Math.round(rating);
  return "★".repeat(full) + "☆".repeat(5 - full);
}

// ── INR format ──────────────────────────────────────────────────────────────
function inr(n) { return Number(n).toLocaleString("en-IN"); }

// ── HOME PAGE ───────────────────────────────────────────────────────────────
async function loadHome() {
  try {
    const res = await fetch(`${API_BASE}/api/catalog`);
    const data = await res.json();
    document.getElementById("stat-policies").textContent = data.total;
    document.getElementById("stat-companies").textContent = Object.keys(data.companies).length;
    renderCompanyGrid(data.companies);
  } catch (e) { console.error(e); }
}

function renderCompanyGrid(companies) {
  const grid = document.getElementById("company-grid");
  grid.innerHTML = "";
  Object.entries(companies).forEach(([company, policies]) => {
    const color = companyColor(company);
    const avgRating = (policies.reduce((s, p) => s + (p.rating || 3.5), 0) / policies.length).toFixed(1);
    const hasFloater = policies.some(p => p.is_family_floater);
    const hasTopup   = policies.some(p => p.is_top_up);
    const hasMaternity = policies.some(p => p.maternity_cover === "yes");
    const card = document.createElement("div");
    card.className = "company-card";
    card.innerHTML = `
      <div class="cc-stripe" style="background:${color}"></div>
      <div class="cc-body">
        <div class="cc-name">${company}</div>
        <div class="cc-count">${policies.length} plan${policies.length > 1 ? "s" : ""} available</div>
        <div class="cc-pills">
          ${hasFloater  ? '<span class="cc-pill">👨‍👩‍👧 Floater</span>' : ""}
          ${hasTopup    ? '<span class="cc-pill orange">🔼 Top-Up</span>' : ""}
          ${hasMaternity? '<span class="cc-pill green">🤰 Maternity</span>' : ""}
        </div>
        <div class="cc-rating">${stars(avgRating)} ${avgRating}</div>
        <div class="cc-view">View all plans →</div>
      </div>`;
    card.addEventListener("click", () => openCompanyModal(company, policies, color));
    grid.appendChild(card);
  });
}

function openCompanyModal(company, policies, color) {
  const modal = document.getElementById("company-modal");
  const content = document.getElementById("modal-content");
  content.innerHTML = `
    <div class="modal-company-name" style="border-left:4px solid ${color};padding-left:12px">${company}</div>
    <div class="modal-policy-count">${policies.length} plans in our catalog</div>
    ${policies.map(p => `
      <div class="modal-policy-item">
        <div>
          <div class="mpi-name">${p.policy_name}${p.policy_variant ? " — " + p.policy_variant : ""}</div>
          <div class="mpi-type">${p.policy_type || "—"}</div>
          <div class="mpi-si">${p.sum_insured_raw || "SI not specified"}</div>
        </div>
        <div class="mpi-right">
          <div class="mpi-rating">${stars(p.rating)} ${p.rating}</div>
          <a class="mpi-brochure" href="${API_BASE}/api/brochure/${p.id}" target="_blank">📄 Brochure</a>
        </div>
      </div>`).join("")}`;
  modal.classList.remove("hidden");
}

function closeModal(e) {
  if (e.target.id === "company-modal") document.getElementById("company-modal").classList.add("hidden");
}

// ── BMI ─────────────────────────────────────────────────────────────────────
function computeBMI() {
  const h = Number(document.getElementById("height_cm").value);
  const w = Number(document.getElementById("weight_kg").value);
  const bmiVal = document.getElementById("bmi-val");
  const bmiLabel = document.getElementById("bmi-label");
  if (!h || !w) { bmiVal.textContent = "—"; bmiLabel.textContent = ""; return null; }
  const bmi = w / ((h / 100) ** 2);
  bmiVal.textContent = bmi.toFixed(1);
  if      (bmi < 18.5) { bmiLabel.textContent = "Underweight"; bmiLabel.style.cssText = "background:#fef3c7;color:#92400e"; }
  else if (bmi < 25)   { bmiLabel.textContent = "Normal";       bmiLabel.style.cssText = "background:#dcfce7;color:#166534"; }
  else if (bmi < 30)   { bmiLabel.textContent = "Overweight";   bmiLabel.style.cssText = "background:#fff7ed;color:#9a3412"; }
  else                 { bmiLabel.textContent = "Obese";         bmiLabel.style.cssText = "background:#fee2e2;color:#991b1b"; }
  return bmi;
}

// ── Profile reader ──────────────────────────────────────────────────────────
function readProfile() {
  const g = id => document.getElementById(id);
  const requirements = [...document.querySelectorAll("#requirements-grid input:checked")].map(c => c.value);
  const existing_conditions = [...document.querySelectorAll("#conditions-grid input:checked")].map(c => c.value);
  return {
    age:                    Number(g("age").value),
    gender:                 g("gender").value,
    marital_status:         g("marital_status").value,
    occupation:             g("occupation").value,
    city_tier:              g("city_tier").value,
    family_floater:         g("family_floater").checked,
    family_size:            Number(g("family_size").value),
    bmi:                    computeBMI(),
    pre_existing_disease:   g("pre_existing_disease").checked,
    existing_conditions,
    smoker:                 g("smoker").checked,
    alcohol:                g("alcohol").checked,
    sum_insured:            Number(g("sum_insured").value),
    budget:                 Number(g("budget").value),
    room_rent_preference:   g("room_rent_preference").value,
    premium_frequency_preference: g("premium_frequency_preference").value,
    is_renewal:             g("is_renewal").checked,
    current_insurer:        g("current_insurer").value,
    current_sum_insured:    Number(g("current_sum_insured").value),
    requirements,
    other_requirement:      g("others_toggle").checked ? g("other_requirement").value : "",
    top_n: 5,
  };
}

// ── Policy card renderer (NO premium field) ─────────────────────────────────
function policyCard(p, idx) {
  const hasScore = p.match_score != null;
  const reasonTags = (p.match_reasons || []).map(r => `<span class="reason-tag">${r}</span>`).join("");

  const meta = [
    ["Type",        p.policy_type || "—"],
    ["Sum Insured", p.sum_insured_raw || "—"],
    ["Rating",      `<span class="stars">${stars(p.rating)}</span> ${p.rating}/5`],
    ["Best For",    p.best_for || "—"],
  ];

  const card = document.createElement("div");
  card.className = "policy-card";
  card.innerHTML = `
    <div class="pc-header">
      ${hasScore ? `<div class="pc-rank">#${idx + 1}</div>` : `<div class="pc-rank">#${idx + 1} Ranked</div>`}
      ${hasScore ? `<div class="pc-score">${p.match_score}% match</div>` : ""}
      <div class="pc-title">${p.policy_name}${p.policy_variant ? " — " + p.policy_variant : ""}</div>
      <div class="pc-company">${p.insurance_company}</div>
    </div>
    <div class="pc-body">
      <div class="pc-meta">
        ${meta.map(([k,v]) => `<span class="pc-meta-key">${k}</span><span class="pc-meta-val">${v}</span>`).join("")}
      </div>
      ${reasonTags ? `<div class="pc-reasons">${reasonTags}</div>` : ""}
      <a class="brochure-btn" href="${API_BASE}/api/brochure/${p.id}" target="_blank" rel="noopener">
        📄 View Policy Brochure (PDF)
      </a>
    </div>`;
  return card;
}

function renderInto(container, recs, emptyMsg) {
  container.innerHTML = "";
  if (!recs || !recs.length) {
    container.innerHTML = `<div class="empty-state"><div class="e-icon">🔍</div><p>${emptyMsg}</p></div>`;
    return;
  }
  recs.forEach((p, i) => container.appendChild(policyCard(p, i)));
}

// ── API calls ────────────────────────────────────────────────────────────────
async function fetchPersonalized(profile) {
  const status = document.getElementById("status");
  status.textContent = "Updating…";
  try {
    const r = await fetch(`${API_BASE}/api/recommend`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(profile) });
    const d = await r.json();
    renderInto(document.getElementById("results"), d.recommendations, "No matching policies found. Try relaxing your filters.");
    status.textContent = `${d.count} matches · just now`;
  } catch { status.textContent = "Error"; }
}

async function fetchTopup(profile) {
  const status = document.getElementById("status-topup");
  status.textContent = "Updating…";
  try {
    const r = await fetch(`${API_BASE}/api/topup`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(profile) });
    const d = await r.json();
    renderInto(document.getElementById("results-topup"), d.recommendations, "No top-up plans found. Try adjusting your sum insured.");
    status.textContent = `${d.count} top-up plans`;
  } catch { status.textContent = "Error"; }
}

async function fetchTop10() {
  const status = document.getElementById("status-top10");
  status.textContent = "Loading…";
  try {
    const r = await fetch(`${API_BASE}/api/top10`);
    const d = await r.json();
    renderInto(document.getElementById("results-top10"), d.recommendations, "No data available.");
    status.textContent = `${d.count} top-rated policies`;
  } catch { status.textContent = "Error"; }
}

let debounce;
function refreshAll() { const p = readProfile(); fetchPersonalized(p); fetchTopup(p); }
function debouncedRefresh() { clearTimeout(debounce); debounce = setTimeout(refreshAll, 320); }

// ── Init ─────────────────────────────────────────────────────────────────────
function init() {
  const g = id => document.getElementById(id);

  // result tabs
  document.querySelectorAll(".rtab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".rtab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".rtab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // sliders
  g("sum_insured").addEventListener("input", () => {
    g("si-val").textContent = "₹" + inr(g("sum_insured").value);
  });
  g("budget").addEventListener("input", () => {
    const v = Number(g("budget").value);
    g("budget-val").textContent = v === 0 ? "No limit" : "₹" + inr(v);
  });

  // toggles
  g("family_floater").addEventListener("change", () => g("family-size-wrap").classList.toggle("hidden", !g("family_floater").checked));
  g("is_renewal").addEventListener("change", () => g("renewal-wrap").classList.toggle("hidden", !g("is_renewal").checked));
  g("others_toggle").addEventListener("change", () => {
    g("other_requirement").classList.toggle("hidden", !g("others_toggle").checked);
    if (!g("others_toggle").checked) g("other_requirement").value = "";
  });

  // BMI
  g("height_cm").addEventListener("input", computeBMI);
  g("weight_kg").addEventListener("input", computeBMI);

  // live updates
  document.querySelectorAll("#profile-form input, #profile-form select")
    .forEach(el => { el.addEventListener("input", debouncedRefresh); el.addEventListener("change", debouncedRefresh); });

  // initial label
  g("si-val").textContent = "₹" + inr(g("sum_insured").value);

  // initial loads
  loadHome();
  window._homeLoaded = true;
  refreshAll();
  fetchTop10();
}

init();
