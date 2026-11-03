/* TripCraft front-end logic. Each page has its own init function (chosen by <body data-page>). */

const formatINR = (n) => "₹" + Math.round(Number(n) || 0).toLocaleString("en-IN");
const readJSON = (id) => JSON.parse(document.getElementById(id).textContent);

/* ================= PAGE 1: PLAN ================= */
function initPlanPage() {
  const form = document.getElementById("trip-form");
  const totalInput = document.getElementById("total_budget");
  const expenseInputs = document.querySelectorAll(".expense");

  function updateBudget() {
    const total = parseFloat(totalInput.value) || 0;
    let planned = 0;
    expenseInputs.forEach((input) => (planned += parseFloat(input.value) || 0));
    const buffer = total - planned;
    const percent = total > 0 ? Math.min((planned / total) * 100, 100) : 0; // avoid divide by zero

    document.getElementById("out-total").textContent = formatINR(total);
    document.getElementById("out-planned").textContent = formatINR(planned);
    document.getElementById("out-buffer").textContent = formatINR(buffer);
    const bar = document.getElementById("budget-bar");
    bar.style.width = percent + "%";
    bar.classList.toggle("danger", planned > total);
    document.getElementById("budget-note").textContent = Math.round(percent) + "% of your budget is allocated.";

    const warning = document.getElementById("budget-warning");
    warning.hidden = !(planned > total);
    if (planned > total) warning.textContent = "Your planned expenses exceed your budget by " + formatINR(planned - total) + ".";
  }
  totalInput.addEventListener("input", updateBudget);
  expenseInputs.forEach((i) => i.addEventListener("input", updateBudget));
  updateBudget();

  // Client-side validation (the server checks again)
  form.addEventListener("submit", (event) => {
    const errors = [];
    form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
    const mark = (name, message) => { errors.push(message); form.elements[name].classList.add("invalid"); };
    if (!form.destination.value.trim()) mark("destination", "Enter a destination.");
    if (!(parseInt(form.days.value) >= 1)) mark("days", "Enter at least 1 day.");
    if (!(parseInt(form.travellers.value) >= 1)) mark("travellers", "Enter at least 1 traveller.");
    if (!form.climate.value) mark("climate", "Choose a climate.");
    if (!form.trip_type.value) mark("trip_type", "Choose a trip type.");
    if (!form.querySelector('input[name="activities"]:checked')) errors.push("Select at least one planned activity.");
    if (!(parseFloat(totalInput.value) > 0)) mark("total_budget", "Enter a total budget above zero.");
    expenseInputs.forEach((i) => { if (parseFloat(i.value) < 0) { errors.push("Expenses cannot be negative."); i.classList.add("invalid"); } });

    const box = document.getElementById("form-errors");
    box.hidden = errors.length === 0;
    box.innerHTML = errors.join("<br>");
    if (errors.length) event.preventDefault();
  });
}

/* ================= PAGE 2: PREPARE ================= */
const PACK_CATEGORIES = ["Clothing", "Footwear", "Toiletries", "Electronics", "Documents", "Health", "Activity Essentials"];

// Rules: [item name, category, reason]
const CLIMATE_RULES = {
  Hot: [["Sunscreen", "Toiletries"], ["Sunglasses", "Activity Essentials"], ["Cap / Hat", "Clothing"],
  ["Light breathable clothes", "Clothing"], ["Water bottle", "Activity Essentials"]],
  Cold: [["Jacket", "Clothing"], ["Sweater", "Clothing"], ["Warm socks", "Clothing"],
  ["Moisturizer", "Toiletries"], ["Layered clothing", "Clothing"]],
  Rainy: [["Umbrella", "Activity Essentials"], ["Raincoat", "Clothing"], ["Waterproof footwear", "Footwear"],
  ["Waterproof pouch", "Activity Essentials"]],
  Moderate: [["Light jacket", "Clothing"], ["Comfortable clothing", "Clothing"]],
};
const TRIP_TYPE_RULES = {
  Adventure: [["Sports shoes", "Footwear"], ["Backpack", "Activity Essentials"], ["Water bottle", "Activity Essentials"], ["First-aid kit", "Health"]],
  Business: [["Formal wear", "Clothing"], ["Formal shoes", "Footwear"], ["Laptop", "Electronics"], ["Laptop charger", "Electronics"]],
  Beach: [["Swimwear", "Clothing"], ["Flip-flops", "Footwear"], ["Sunscreen", "Toiletries"], ["Beach towel", "Activity Essentials"]],
  Family: [["Comfortable clothes", "Clothing"], ["Basic medicines", "Health"], ["Extra essentials pouch", "Activity Essentials"]],
  Leisure: [["Casual clothing", "Clothing"], ["Comfortable footwear", "Footwear"]],
};
const ACTIVITY_RULES = {
  "Sightseeing": [["Comfortable footwear", "Footwear"], ["Day bag", "Activity Essentials"], ["Sunglasses", "Activity Essentials"]],
  "Beach": [["Swimwear", "Clothing"], ["Sunscreen", "Toiletries"], ["Flip-flops", "Footwear"], ["Beach towel", "Activity Essentials"]],
  "Trekking": [["Sports shoes", "Footwear"], ["Backpack", "Activity Essentials"], ["Water bottle", "Activity Essentials"],
  ["First-aid kit", "Health"], ["Breathable clothes", "Clothing"]],
  "Temple / Religious place": [["Modest clothing", "Clothing"], ["Scarf / shawl", "Clothing"], ["Comfortable footwear", "Footwear"]],
  "Shopping": [["Foldable shopping bag", "Activity Essentials"], ["Comfortable footwear", "Footwear"]],
  "Adventure activity": [["Sportswear", "Clothing"], ["Water bottle", "Activity Essentials"], ["First-aid kit", "Health"]],
  "Formal / Business event": [["Formal outfit", "Clothing"], ["Formal footwear", "Footwear"]],
  "Nightlife": [["Evening outfit", "Clothing"], ["Evening footwear", "Footwear"]],
};

function buildPackingList(trip) {
  const list = [];
  const seen = new Set(); // stops the same item being added twice by different rules
  function add(name, category, reason) {
    const key = name.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    list.push({ item_name: name, category, reason, packed: 0, custom_item: 0 });
  }
  const days = trip.days;

  // Basic items (quantities depend on the number of days)
  add("ID / travel documents", "Documents", "Always carry it");
  add("Phone charger", "Electronics", "Basic essential");
  add("Toiletries", "Toiletries", "Basic essential");
  add("Basic medicines", "Health", "Basic essential");
  add(days + " Tops / Shirts", "Clothing", "One per day");
  add(days + " Sets of innerwear", "Clothing", "One set per day");
  add(days + " Pairs of socks", "Clothing", "One pair per day");
  add(Math.max(2, Math.ceil(days / 2)) + " Bottoms (pants / shorts)", "Clothing", "Re-wear every 2 days");
  add("Everyday footwear", "Footwear", "Basic essential");

  (CLIMATE_RULES[trip.climate] || []).forEach(([n, c]) => add(n, c, trip.climate + " weather essential"));
  (TRIP_TYPE_RULES[trip.trip_type] || []).forEach(([n, c]) => add(n, c, trip.trip_type + " trip essential"));
  trip.activities.forEach((act) => (ACTIVITY_RULES[act] || []).forEach(([n, c]) => add(n, c, "For " + act.toLowerCase())));
  return list;
}

function initPreparePage() {
  const trip = readJSON("trip-data");
  let items = readJSON("packing-data");
  let activeFilter = "All";

  function savePacking() {
    fetch("/save-packing/" + trip.id, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
    }).catch(() => alert("Could not save your packing list. Is the server running?"));
  }

  // First visit: nothing saved yet, so generate the list from the rules and store it
  if (items.length === 0) { items = buildPackingList(trip); savePacking(); }

  function render() {
    const packed = items.filter((i) => i.packed).length;
    const percent = items.length ? Math.round((packed / items.length) * 100) : 0;
    document.getElementById("pack-text").textContent = `${packed} of ${items.length} items packed (${percent}%)`;
    document.getElementById("pack-bar").style.width = percent + "%";

    // Filter chips
    const filters = document.getElementById("filters");
    filters.innerHTML = "";
    ["All", ...PACK_CATEGORIES].forEach((name) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip" + (name === activeFilter ? " active" : "");
      chip.textContent = name;
      chip.onclick = () => { activeFilter = name; render(); };
      filters.appendChild(chip);
    });

    // Category cards
    const board = document.getElementById("packing-board");
    board.innerHTML = "";
    PACK_CATEGORIES.filter((c) => activeFilter === "All" || activeFilter === c).forEach((category) => {
      const inCategory = items.filter((i) => i.category === category);
      if (!inCategory.length) return;
      const section = document.createElement("div");
      section.className = "pack-category";
      const doneCount = inCategory.filter((i) => i.packed).length;
      section.innerHTML = `<h3>${category} <span class="muted">(${doneCount}/${inCategory.length})</span></h3><div class="pack-grid"></div>`;
      inCategory.forEach((item) => section.querySelector(".pack-grid").appendChild(makeCard(item)));
      board.appendChild(section);
    });
  }

  function makeCard(item) {
    const card = document.createElement("div");
    card.className = "item-card" + (item.packed ? " packed" : "");
    const name = document.createElement("div"); name.className = "item-name"; name.textContent = item.item_name;
    const reason = document.createElement("div"); reason.className = "item-reason";
    reason.textContent = item.custom_item ? "Custom item" : item.reason;
    const button = document.createElement("button");
    button.className = "pack-btn"; button.type = "button";
    button.textContent = item.packed ? "✓ Packed (undo)" : "Mark Packed";
    button.onclick = () => { item.packed = item.packed ? 0 : 1; savePacking(); render(); };
    card.append(name, reason, button);
    if (item.custom_item) {
      const del = document.createElement("button");
      del.className = "icon-btn"; del.type = "button"; del.title = "Delete item"; del.textContent = "✕";
      del.onclick = () => { items = items.filter((i) => i !== item); savePacking(); render(); };
      card.appendChild(del);
    }
    return card;
  }

  // Custom item form
  const categorySelect = document.getElementById("custom-category");
  PACK_CATEGORIES.forEach((c) => categorySelect.add(new Option(c, c)));
  const nameInput = document.getElementById("custom-name");
  function addCustom() {
    const name = nameInput.value.trim();
    if (!name) { nameInput.classList.add("invalid"); return; }
    nameInput.classList.remove("invalid");
    items.push({ item_name: name, category: categorySelect.value, reason: "Custom item", packed: 0, custom_item: 1 });
    nameInput.value = "";
    savePacking(); render();
  }
  document.getElementById("custom-add").onclick = addCustom;
  nameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addCustom(); } });

  render();
}

/* ================= PAGE 3: TRACK ================= */
function initTrackPage() {
  const saved = readJSON("expense-data"); // {dayNumber: {food: .., ...}}
  const daySelect = document.getElementById("expense-day");
  const fields = ["food", "local_transport", "sightseeing", "shopping", "miscellaneous"];
  // When a day with saved expenses is chosen, pre-fill the form so it can be updated
  function fillForm() {
    const entry = saved[daySelect.value];
    fields.forEach((f) => (document.querySelector(`[name="${f}"]`).value = entry ? entry[f] : 0));
  }
  daySelect.addEventListener("change", fillForm);
  fillForm();
}

const pageInit = { plan: initPlanPage, prepare: initPreparePage, track: initTrackPage };
const currentPage = document.body.dataset.page;
if (pageInit[currentPage]) pageInit[currentPage]();
