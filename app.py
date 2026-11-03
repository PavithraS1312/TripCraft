"""TripCraft - Smart Travel Planning Assistant (Flask + SQLite)."""
import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, flash, jsonify, abort

app = Flask(__name__)
app.secret_key = "tripcraft-dev-key"  # needed for flash messages
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tripcraft.db")

ACTIVITY_OPTIONS = ["Sightseeing", "Beach", "Trekking", "Temple / Religious place",
                    "Shopping", "Adventure activity", "Formal / Business event",
                    "Nightlife", "General leisure"]
CLIMATES = ["Hot", "Cold", "Rainy", "Moderate"]
TRIP_TYPES = ["Leisure", "Adventure", "Business", "Beach", "Family"]
TIMES = ["Morning", "Afternoon", "Evening"]
ITINERARY_CATEGORIES = ["Sightseeing", "Food", "Shopping", "Adventure", "Transport", "Other"]
# Daily expense categories: (db column, label, matching budget column in trips)
DAILY_CATEGORIES = [("food", "Food", "food_budget"),
                    ("local_transport", "Local Transport", "local_transport_budget"),
                    ("sightseeing", "Sightseeing / Activities", "sightseeing_budget"),
                    ("shopping", "Shopping", "shopping_budget"),
                    ("miscellaneous", "Miscellaneous", "miscellaneous_budget")]

SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destination TEXT NOT NULL, days INTEGER NOT NULL, travellers INTEGER NOT NULL,
    climate TEXT NOT NULL, trip_type TEXT NOT NULL, activities_selected TEXT NOT NULL,
    total_budget REAL NOT NULL, travel_budget REAL DEFAULT 0, accommodation_budget REAL DEFAULT 0,
    food_budget REAL DEFAULT 0, local_transport_budget REAL DEFAULT 0,
    sightseeing_budget REAL DEFAULT 0, shopping_budget REAL DEFAULT 0,
    miscellaneous_budget REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS packing_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    item_name TEXT NOT NULL, category TEXT NOT NULL, reason TEXT,
    packed INTEGER DEFAULT 0, custom_item INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS itinerary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL, time_of_day TEXT NOT NULL, activity_name TEXT NOT NULL,
    category TEXT NOT NULL, estimated_expense REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS daily_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL, food REAL DEFAULT 0, local_transport REAL DEFAULT 0,
    sightseeing REAL DEFAULT 0, shopping REAL DEFAULT 0, miscellaneous REAL DEFAULT 0,
    total REAL DEFAULT 0, UNIQUE (trip_id, day_number));
"""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")  # SQLite needs this for every connection
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


def get_trip_or_404(trip_id):
    trip = get_db().execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if trip is None:
        abort(404)
    return trip


def to_number(value, default=0.0):
    """Convert form text to a non-negative number (bad input becomes default)."""
    try:
        number = float(value)
        return number if number >= 0 else default
    except (TypeError, ValueError):
        return default


# ---------- template filters (₹ formatting with Indian digit grouping) ----------
@app.template_filter("inr")
def inr(value):
    amount = round(float(value or 0))
    digits = str(abs(amount))
    if len(digits) > 3:
        head, tail, parts = digits[:-3], digits[-3:], []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    return ("-" if amount < 0 else "") + "₹" + digits


@app.template_filter("inr_signed")
def inr_signed(value):
    return ("+" if round(float(value or 0)) > 0 else "") + inr(value)


# ---------- Page 1: Plan ----------
@app.route("/")
def home():
    return redirect(url_for("plan"))


@app.route("/plan")
def plan():
    return render_template("plan.html", activities=ACTIVITY_OPTIONS,
                           climates=CLIMATES, trip_types=TRIP_TYPES)


@app.route("/create-trip", methods=["POST"])
def create_trip():
    f = request.form
    destination = f.get("destination", "").strip()
    days = int(to_number(f.get("days")))
    travellers = int(to_number(f.get("travellers")))
    activities = [a for a in f.getlist("activities") if a in ACTIVITY_OPTIONS]
    total_budget = to_number(f.get("total_budget"))

    errors = []
    if not destination:
        errors.append("Destination is required.")
    if not 1 <= days <= 60:
        errors.append("Number of days must be between 1 and 60.")
    if travellers < 1:
        errors.append("Number of travellers must be at least 1.")
    if f.get("climate") not in CLIMATES or f.get("trip_type") not in TRIP_TYPES:
        errors.append("Please choose a climate and a trip type.")
    if not activities:
        errors.append("Select at least one planned activity.")
    if total_budget <= 0:
        errors.append("Total trip budget must be greater than zero.")
    if errors:
        for e in errors:
            flash(e)
        return redirect(url_for("plan"))

    db = get_db()
    cursor = db.execute(
        """INSERT INTO trips (destination, days, travellers, climate, trip_type, activities_selected,
           total_budget, travel_budget, accommodation_budget, food_budget, local_transport_budget,
           sightseeing_budget, shopping_budget, miscellaneous_budget)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (destination, days, travellers, f["climate"], f["trip_type"], ",".join(activities),
         total_budget, to_number(f.get("travel")), to_number(f.get("accommodation")),
         to_number(f.get("food")), to_number(f.get("local_transport")),
         to_number(f.get("sightseeing")), to_number(f.get("shopping")),
         to_number(f.get("miscellaneous"))))
    db.commit()
    return redirect(url_for("prepare", trip_id=cursor.lastrowid))


# ---------- Page 2: Prepare ----------
@app.route("/prepare/<int:trip_id>")
def prepare(trip_id):
    db = get_db()
    trip = get_trip_or_404(trip_id)
    packing = [dict(r) for r in db.execute(
        "SELECT item_name, category, reason, packed, custom_item FROM packing_items WHERE trip_id = ? ORDER BY id",
        (trip_id,))]
    rows = db.execute(
        """SELECT * FROM itinerary WHERE trip_id = ? ORDER BY day_number,
           CASE time_of_day WHEN 'Morning' THEN 1 WHEN 'Afternoon' THEN 2 ELSE 3 END, id""",
        (trip_id,)).fetchall()
    days = {d: [] for d in range(1, trip["days"] + 1)}
    for row in rows:
        days.setdefault(row["day_number"], []).append(row)
    trip_data = {"id": trip["id"], "days": trip["days"], "climate": trip["climate"],
                 "trip_type": trip["trip_type"],
                 "activities": trip["activities_selected"].split(",")}
    return render_template("prepare.html", trip=trip, trip_data=trip_data, packing=packing,
                           itinerary_days=days, itinerary_total=sum(r["estimated_expense"] for r in rows),
                           times=TIMES, categories=ITINERARY_CATEGORIES)


@app.route("/save-packing/<int:trip_id>", methods=["POST"])
def save_packing(trip_id):
    """Replace the saved packing list with the list sent by JavaScript."""
    get_trip_or_404(trip_id)
    items = (request.get_json(silent=True) or {}).get("items", [])
    db = get_db()
    db.execute("DELETE FROM packing_items WHERE trip_id = ?", (trip_id,))
    db.executemany(
        "INSERT INTO packing_items (trip_id, item_name, category, reason, packed, custom_item) VALUES (?,?,?,?,?,?)",
        [(trip_id, str(i.get("item_name", ""))[:80], str(i.get("category", "Activity Essentials")),
          str(i.get("reason", ""))[:120], 1 if i.get("packed") else 0, 1 if i.get("custom_item") else 0)
         for i in items if str(i.get("item_name", "")).strip()])
    db.commit()
    return jsonify(ok=True, count=len(items))


@app.route("/add-itinerary/<int:trip_id>", methods=["POST"])
def add_itinerary(trip_id):
    trip = get_trip_or_404(trip_id)
    f = request.form
    day = int(to_number(f.get("day_number")))
    name = f.get("activity_name", "").strip()
    if not 1 <= day <= trip["days"] or not name or f.get("time_of_day") not in TIMES \
            or f.get("category") not in ITINERARY_CATEGORIES:
        flash("Please fill in all itinerary fields correctly.")
    else:
        db = get_db()
        db.execute("""INSERT INTO itinerary (trip_id, day_number, time_of_day, activity_name, category,
                      estimated_expense) VALUES (?,?,?,?,?,?)""",
                   (trip_id, day, f["time_of_day"], name, f["category"], to_number(f.get("estimated_expense"))))
        db.commit()
    return redirect(url_for("prepare", trip_id=trip_id) + "#itinerary")


@app.route("/delete-itinerary/<int:trip_id>/<int:item_id>", methods=["POST"])
def delete_itinerary(trip_id, item_id):
    db = get_db()
    db.execute("DELETE FROM itinerary WHERE id = ? AND trip_id = ?", (item_id, trip_id))
    db.commit()
    return redirect(url_for("prepare", trip_id=trip_id) + "#itinerary")


# ---------- Page 3: Track ----------
def build_suggestions(trip, actual_by_category, days_done, remaining_budget):
    """Simple rule-based tips: compare actual spend with the plan for the days completed."""
    tips = []
    messages = {
        "food": "Food spending is above plan. Try choosing lower-cost dining options during the remaining days.",
        "local_transport": "Local transport costs are higher than expected. Consider grouping nearby activities together.",
        "sightseeing": "Activity expenses are above plan. Consider prioritizing free or lower-cost attractions.",
        "shopping": "Shopping expenses are above the planned amount. Consider reducing shopping on upcoming days.",
    }
    for column, label, budget_column in DAILY_CATEGORIES:
        # Planned allowance for the days already completed (budget spread evenly over the trip)
        planned_so_far = trip[budget_column] / trip["days"] * days_done
        if column in messages and actual_by_category[column] > planned_so_far:
            tips.append(messages[column])
    if remaining_budget < 0.2 * trip["total_budget"]:
        tips.append("Your remaining budget is limited. Reduce non-essential spending on shopping and miscellaneous items.")
    if not tips:
        tips.append("Your spending is currently within the planned budget.")
    return tips


@app.route("/track/<int:trip_id>")
def track(trip_id):
    db = get_db()
    trip = get_trip_or_404(trip_id)
    packed = db.execute("SELECT COUNT(*) AS total, COALESCE(SUM(packed),0) AS done FROM packing_items WHERE trip_id = ?",
                        (trip_id,)).fetchone()
    expenses = {r["day_number"]: dict(r) for r in db.execute(
        "SELECT * FROM daily_expenses WHERE trip_id = ?", (trip_id,))}

    planned_expense = sum(trip[c] for c in ("travel_budget", "accommodation_budget", "food_budget",
                                            "local_transport_budget", "sightseeing_budget",
                                            "shopping_budget", "miscellaneous_budget"))
    # Planned approximate spend per day = the five daily budgets spread across the trip days
    planned_per_day = sum(trip[c[2]] for c in DAILY_CATEGORIES) / trip["days"]

    day_cards = []
    for day in range(1, trip["days"] + 1):
        entry = expenses.get(day)
        day_cards.append({"day": day, "entry": entry, "planned": planned_per_day,
                          "difference": (entry["total"] - planned_per_day) if entry else None})

    days_done = len(expenses)
    actual_spent = sum(e["total"] for e in expenses.values())
    actual_by_category = {c[0]: sum(e[c[0]] for e in expenses.values()) for c in DAILY_CATEGORIES}
    remaining_budget = trip["total_budget"] - actual_spent
    remaining_days = max(trip["days"] - days_done, 0)
    daily_limit = remaining_budget / remaining_days if remaining_days > 0 else 0  # avoid division by zero

    suggestions = build_suggestions(trip, actual_by_category, days_done, remaining_budget) if days_done else \
        ["Add your first day's expenses to see spending suggestions."]
    return render_template("track.html", trip=trip, packed=packed, planned_expense=planned_expense,
                           day_cards=day_cards, categories=DAILY_CATEGORIES, expenses=expenses,
                           actual_spent=actual_spent, remaining_budget=remaining_budget,
                           remaining_days=remaining_days, daily_limit=daily_limit,
                           suggestions=suggestions, days_done=days_done)


@app.route("/add-expense/<int:trip_id>", methods=["POST"])
def add_expense(trip_id):
    trip = get_trip_or_404(trip_id)
    f = request.form
    day = int(to_number(f.get("day_number")))
    if not 1 <= day <= trip["days"]:
        flash("Choose a valid day number.")
        return redirect(url_for("track", trip_id=trip_id))
    values = {c[0]: to_number(f.get(c[0])) for c in DAILY_CATEGORIES}
    total = sum(values.values())
    db = get_db()
    # One row per day: insert it, or update it if that day was already saved
    db.execute("""INSERT INTO daily_expenses (trip_id, day_number, food, local_transport, sightseeing,
                  shopping, miscellaneous, total) VALUES (?,?,?,?,?,?,?,?)
                  ON CONFLICT(trip_id, day_number) DO UPDATE SET food=excluded.food,
                  local_transport=excluded.local_transport, sightseeing=excluded.sightseeing,
                  shopping=excluded.shopping, miscellaneous=excluded.miscellaneous, total=excluded.total""",
               (trip_id, day, values["food"], values["local_transport"], values["sightseeing"],
                values["shopping"], values["miscellaneous"], total))
    db.commit()
    flash(f"Day {day} expenses saved.")
    return redirect(url_for("track", trip_id=trip_id))


init_db()  # create tables automatically on first run

if __name__ == "__main__":
    app.run(debug=True, port=5001)
