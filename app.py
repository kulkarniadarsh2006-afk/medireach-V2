"""
MediReach AI v2 — Flask Backend
AI-Powered Rural Healthcare Medicine Distribution Platform
Matches Pega Blueprint: 11 Personas | 8 Workflows | 14 Data Objects
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta
import random
import math

app = Flask(__name__)
CORS(app)
app.secret_key = "medireach_ai_2026"

# Google OAuth has been removed in favor of Mobile OTP Auth.

# ─────────────────────────────────────────────
# MOCK DATA — 14 DATA OBJECTS FROM PEGA BLUEPRINT
# ─────────────────────────────────────────────

VILLAGES = [
    {"id": "V001", "name": "Raichur", "population": 45200, "district": "Raichur", "lat": 16.2, "lng": 77.4, "phc": "Raichur PHC", "growth_rate": 1.8, "age_distribution": {"0-14": 32, "15-60": 55, "60+": 13}},
    {"id": "V002", "name": "Gulbarga", "population": 38600, "district": "Kalaburagi", "lat": 17.3, "lng": 76.8, "phc": "Gulbarga PHC", "growth_rate": 2.1, "age_distribution": {"0-14": 30, "15-60": 57, "60+": 13}},
    {"id": "V003", "name": "Koppal", "population": 28400, "district": "Koppal", "lat": 15.4, "lng": 76.2, "phc": "Koppal PHC", "growth_rate": 1.5, "age_distribution": {"0-14": 35, "15-60": 52, "60+": 13}},
    {"id": "V004", "name": "Bijapur", "population": 52000, "district": "Vijayapura", "lat": 16.8, "lng": 75.7, "phc": "Bijapur PHC", "growth_rate": 2.3, "age_distribution": {"0-14": 28, "15-60": 59, "60+": 13}},
    {"id": "V005", "name": "Bellary", "population": 33100, "district": "Ballari", "lat": 15.1, "lng": 76.9, "phc": "Bellary PHC", "growth_rate": 1.9, "age_distribution": {"0-14": 31, "15-60": 56, "60+": 13}},
    {"id": "V006", "name": "Yadgir", "population": 31500, "district": "Yadgir", "lat": 16.8, "lng": 77.1, "phc": "Yadgir PHC", "growth_rate": 1.6, "age_distribution": {"0-14": 33, "15-60": 54, "60+": 13}},
    {"id": "V007", "name": "Dharwad", "population": 41000, "district": "Dharwad", "lat": 15.5, "lng": 75.0, "phc": "Dharwad PHC", "growth_rate": 2.0, "age_distribution": {"0-14": 29, "15-60": 58, "60+": 13}},
    {"id": "V008", "name": "Haveri", "population": 22300, "district": "Haveri", "lat": 14.8, "lng": 75.4, "phc": "Haveri PHC", "growth_rate": 1.4, "age_distribution": {"0-14": 34, "15-60": 53, "60+": 13}},
]

MEDICINES = [
    {"id": "M001", "name": "Paracetamol 500mg", "category": "Antipyretic", "unit": "Tablets", "critical": True},
    {"id": "M002", "name": "Chloroquine 250mg", "category": "Antimalarial", "unit": "Tablets", "critical": True},
    {"id": "M003", "name": "ORS Sachets", "category": "Rehydration", "unit": "Sachets", "critical": True},
    {"id": "M004", "name": "Amoxicillin 500mg", "category": "Antibiotic", "unit": "Capsules", "critical": True},
    {"id": "M005", "name": "Metformin 500mg", "category": "Antidiabetic", "unit": "Tablets", "critical": False},
    {"id": "M006", "name": "Amlodipine 5mg", "category": "Antihypertensive", "unit": "Tablets", "critical": False},
    {"id": "M007", "name": "Vitamin D3 1000IU", "category": "Supplement", "unit": "Capsules", "critical": False},
    {"id": "M008", "name": "Albendazole 400mg", "category": "Anthelmintic", "unit": "Tablets", "critical": False},
    {"id": "M009", "name": "Dexamethasone 4mg", "category": "Corticosteroid", "unit": "Tablets", "critical": True},
    {"id": "M010", "name": "Artemether+Lumef.", "category": "Antimalarial", "unit": "Tablets", "critical": True},
]

INVENTORY_DATA = {
    "V001": {"M001": 850, "M002": 120, "M003": 200, "M004": 340, "M005": 520, "M006": 380, "M007": 180, "M008": 290, "M009": 95, "M010": 60},
    "V002": {"M001": 1200, "M002": 80, "M003": 350, "M004": 180, "M005": 420, "M006": 310, "M007": 220, "M008": 190, "M009": 140, "M010": 45},
    "V003": {"M001": 320, "M002": 45, "M003": 80, "M004": 90, "M005": 280, "M006": 200, "M007": 90, "M008": 120, "M009": 30, "M010": 20},
    "V004": {"M001": 1500, "M002": 200, "M003": 450, "M004": 400, "M005": 650, "M006": 480, "M007": 300, "M008": 350, "M009": 180, "M010": 90},
    "V005": {"M001": 600, "M002": 95, "M003": 150, "M004": 220, "M005": 360, "M006": 270, "M007": 140, "M008": 210, "M009": 70, "M010": 35},
    "V006": {"M001": 280, "M002": 35, "M003": 70, "M004": 110, "M005": 190, "M006": 150, "M007": 80, "M008": 95, "M009": 25, "M010": 15},
    "V007": {"M001": 950, "M002": 150, "M003": 280, "M004": 310, "M005": 490, "M006": 360, "M007": 200, "M008": 260, "M009": 120, "M010": 55},
    "V008": {"M001": 410, "M002": 60, "M003": 100, "M004": 130, "M005": 230, "M006": 180, "M007": 110, "M008": 140, "M009": 45, "M010": 25},
}

DISEASE_OUTBREAKS = [
    {"id": "DO001", "village_id": "V001", "disease": "Dengue", "affected": 234, "severity": "High", "spread_rate": 1.3, "started": "2026-05-28"},
    {"id": "DO002", "village_id": "V003", "disease": "Malaria", "affected": 189, "severity": "Critical", "spread_rate": 1.6, "started": "2026-05-30"},
    {"id": "DO003", "village_id": "V006", "disease": "Typhoid", "affected": 67, "severity": "Medium", "spread_rate": 1.1, "started": "2026-06-01"},
    {"id": "DO004", "village_id": "V002", "disease": "Cholera", "affected": 45, "severity": "High", "spread_rate": 1.4, "started": "2026-06-02"},
]

WEATHER_DATA = {
    "V001": {"temp": 38, "rainfall": 12, "humidity": 78, "alert": "Heat Wave", "road_condition": "Good"},
    "V002": {"temp": 36, "rainfall": 5, "humidity": 65, "alert": None, "road_condition": "Good"},
    "V003": {"temp": 35, "rainfall": 45, "humidity": 88, "alert": "Heavy Rain", "road_condition": "Poor"},
    "V004": {"temp": 37, "rainfall": 8, "humidity": 70, "alert": None, "road_condition": "Good"},
    "V005": {"temp": 39, "rainfall": 3, "humidity": 60, "alert": "Heat Wave", "road_condition": "Fair"},
    "V006": {"temp": 34, "rainfall": 62, "humidity": 92, "alert": "Flood Risk", "road_condition": "Critical"},
    "V007": {"temp": 33, "rainfall": 18, "humidity": 72, "alert": None, "road_condition": "Good"},
    "V008": {"temp": 36, "rainfall": 9, "humidity": 68, "alert": None, "road_condition": "Fair"},
}

TRANSPORTATION = [
    {"id": "T001", "type": "Refrigerated Van", "capacity": 500, "available": True, "location": "Raichur Depot", "status": "Idle"},
    {"id": "T002", "type": "Medical Truck", "capacity": 1200, "available": True, "location": "Gulbarga Hub", "status": "Idle"},
    {"id": "T003", "type": "Motorcycle", "capacity": 50, "available": True, "location": "Koppal", "status": "En Route"},
    {"id": "T004", "type": "Medical Truck", "capacity": 1200, "available": False, "location": "Bijapur", "status": "Maintenance"},
    {"id": "T005", "type": "Ambulance", "capacity": 200, "available": True, "location": "Bellary PHC", "status": "Idle"},
    {"id": "T006", "type": "Drone Delivery", "capacity": 10, "available": True, "location": "Central Hub", "status": "Ready"},
]

PERSONAS = [
    {"id": "P001", "role": "Village Healthcare Worker", "icon": "🏥", "color": "#2563EB", "access": ["demand", "shortage", "inventory"]},
    {"id": "P002", "role": "Medicine Inventory Manager", "icon": "💊", "color": "#06B6D4", "access": ["inventory", "transfers", "audit"]},
    {"id": "P003", "role": "Distribution Planner", "icon": "📋", "color": "#10B981", "access": ["demand", "transfers", "schedule"]},
    {"id": "P004", "role": "Transportation Coordinator", "icon": "🚚", "color": "#8B5CF6", "access": ["schedule", "routes", "vehicles"]},
    {"id": "P005", "role": "PHC Administrator", "icon": "🏛️", "color": "#F59E0B", "access": ["all"]},
    {"id": "P006", "role": "Rural Patient", "icon": "👤", "color": "#64748B", "access": ["status"]},
    {"id": "P007", "role": "District Health Officer", "icon": "👨‍⚕️", "color": "#EF4444", "access": ["all", "reports"]},
    {"id": "P008", "role": "Data Analyst", "icon": "📊", "color": "#2563EB", "access": ["analytics", "reports"]},
    {"id": "P009", "role": "Supply Chain Manager", "icon": "🔗", "color": "#06B6D4", "access": ["transfers", "schedule", "audit"]},
    {"id": "P010", "role": "Emergency Coordinator", "icon": "🚨", "color": "#EF4444", "access": ["emergency", "routes"]},
    {"id": "P011", "role": "Government Inspector", "icon": "🏛️", "color": "#10B981", "access": ["reports", "audit", "analytics"]},
]

# ─────────────────────────────────────────────
# AI ENGINE — PREDICTION LOGIC
# ─────────────────────────────────────────────

def get_daily_consumption(village_id, medicine_id):
    """Calculate base daily consumption from population & historical data"""
    village = next((v for v in VILLAGES if v["id"] == village_id), None)
    if not village:
        return 0
    pop = village["population"]
    base_rates = {"M001": 0.015, "M002": 0.004, "M003": 0.006, "M004": 0.005,
                  "M005": 0.008, "M006": 0.007, "M007": 0.003, "M008": 0.002,
                  "M009": 0.002, "M010": 0.003}
    return round(pop * base_rates.get(medicine_id, 0.003))

def get_outbreak_multiplier(village_id):
    """Returns demand multiplier based on active outbreaks"""
    outbreak = next((d for d in DISEASE_OUTBREAKS if d["village_id"] == village_id), None)
    if not outbreak:
        return 1.0
    severity_mult = {"Critical": 2.2, "High": 1.7, "Medium": 1.3, "Low": 1.1}
    return severity_mult.get(outbreak["severity"], 1.0)

def get_weather_multiplier(village_id):
    """Returns demand multiplier based on weather conditions"""
    weather = WEATHER_DATA.get(village_id, {})
    alert = weather.get("alert")
    mult = {"Heat Wave": 1.3, "Heavy Rain": 1.2, "Flood Risk": 1.4}.get(alert, 1.0)
    road = weather.get("road_condition", "Good")
    if road == "Critical":
        mult += 0.3
    elif road == "Poor":
        mult += 0.1
    return mult

def predict_demand(village_id, medicine_id, days):
    """Core AI prediction engine"""
    base = get_daily_consumption(village_id, medicine_id)
    outbreak_mult = get_outbreak_multiplier(village_id)
    weather_mult = get_weather_multiplier(village_id)
    seasonal_mult = 1.15  # Monsoon season
    total_demand = round(base * outbreak_mult * weather_mult * seasonal_mult * days)
    return max(1, total_demand)

def calculate_risk_level(current_stock, daily_demand):
    """Calculate shortage risk level"""
    if daily_demand == 0:
        return "Safe", 999
    days_remaining = current_stock / daily_demand
    if days_remaining <= 2:
        return "Critical", round(days_remaining, 1)
    elif days_remaining <= 5:
        return "High", round(days_remaining, 1)
    elif days_remaining <= 10:
        return "Medium", round(days_remaining, 1)
    return "Low", round(days_remaining, 1)

# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    stats = {
        "villages": len(VILLAGES),
        "medicines": len(MEDICINES),
        "outbreaks": len(DISEASE_OUTBREAKS),
        "personas": len(PERSONAS),
        "workflows": 8,
        "data_objects": 14,
    }
    return render_template("index.html", stats=stats, personas=PERSONAS)

@app.route("/dashboard")
def dashboard():
    persona = request.args.get("persona", "PHC Administrator")
    total_alerts = sum(1 for v in VILLAGES for m in MEDICINES
                       if calculate_risk_level(
                           INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0),
                           get_daily_consumption(v["id"], m["id"])
                       )[0] in ["Critical", "High"])
    availability = []
    for v in VILLAGES:
        inv = INVENTORY_DATA.get(v["id"], {})
        total_stock = sum(inv.values())
        max_stock = sum(get_daily_consumption(v["id"], m["id"]) * 30 for m in MEDICINES)
        pct = min(100, round((total_stock / max(max_stock, 1)) * 100))
        availability.append({"village": v["name"], "pct": pct})
    avg_availability = round(sum(a["pct"] for a in availability) / len(availability))
    active_outbreaks = len(DISEASE_OUTBREAKS)
    return render_template("dashboard.html",
                           persona=persona, personas=PERSONAS,
                           villages=VILLAGES, medicines=MEDICINES,
                           total_alerts=total_alerts,
                           avg_availability=avg_availability,
                           active_outbreaks=active_outbreaks,
                           outbreaks=DISEASE_OUTBREAKS,
                           weather=WEATHER_DATA,
                           inventory=INVENTORY_DATA)

@app.route("/demand")
def demand_page():
    return render_template("demand.html", villages=VILLAGES, medicines=MEDICINES, personas=PERSONAS)

@app.route("/shortage")
def shortage_page():
    return render_template("shortage.html", villages=VILLAGES, medicines=MEDICINES, personas=PERSONAS)

@app.route("/transfers")
def transfers_page():
    return render_template("transfers.html", villages=VILLAGES, medicines=MEDICINES, personas=PERSONAS)

@app.route("/schedule")
def schedule_page():
    return render_template("schedule.html", villages=VILLAGES, medicines=MEDICINES,
                           transport=TRANSPORTATION, personas=PERSONAS)

@app.route("/emergency")
def emergency_page():
    return render_template("emergency.html", villages=VILLAGES, medicines=MEDICINES,
                           outbreaks=DISEASE_OUTBREAKS, personas=PERSONAS)

@app.route("/inventory-audit")
def inventory_audit_page():
    return render_template("inventory.html", villages=VILLAGES, medicines=MEDICINES,
                           inventory=INVENTORY_DATA, personas=PERSONAS)

@app.route("/analytics")
def analytics_page():
    return render_template("analytics.html", villages=VILLAGES, medicines=MEDICINES, personas=PERSONAS)

@app.route("/robots.txt")
def robots_txt():
    domain = request.url_root
    content = f"User-agent: *\nAllow: /\nSitemap: {domain}sitemap.xml\n"
    return app.response_class(content, mimetype="text/plain")

@app.route("/sitemap.xml")
def sitemap_xml():
    domain = request.url_root
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{domain}</loc>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{domain}login</loc>
    <priority>0.8</priority>
  </url>
</urlset>"""
    return app.response_class(xml, mimetype="application/xml")

# ─────────────────────────────────────────────
# MOBILE OTP AUTHENTICATION SYSTEM
# ─────────────────────────────────────────────

@app.context_processor
def inject_user():
    return dict(user=session.get("user"))

@app.before_request
def enforce_login():
    allowed_endpoints = ["index", "login_page", "api_auth_mobile_login", "static", "robots_txt", "sitemap_xml"]
    if request.endpoint and request.endpoint not in allowed_endpoints:
        if request.path.startswith("/api/"):
            if "user" not in session:
                return jsonify({"error": "Unauthorized"}), 401
        else:
            if "user" not in session:
                return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/api/auth/mobile-login", methods=["POST"])
def api_auth_mobile_login():
    data = request.get_json() or {}
    mobile = data.get("mobile", "").strip()
    otp = data.get("otp", "").strip()
    
    if not mobile or len(mobile) < 10:
        return jsonify({"success": False, "error": "Invalid mobile number. Must be 10 digits."}), 400
        
    # Hackathon Demo Mode: Accept OTP 123456
    if otp == "123456":
        session["user"] = {
            "name": "Adarsh",
            "email": "adarsh@medireach.ai",
            "mobile": f"+91 {mobile[-10:]}",
            "given_name": "Adarsh",
            "role": "PHC Administrator"
        }
        return jsonify({"success": True, "redirect": url_for("dashboard")})
        
    return jsonify({"success": False, "error": "Invalid verification code. Use 123456 for Demo."}), 401

@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.pop("user", None)
    return jsonify({"success": True})

@app.route("/api/settings/save-client-id", methods=["POST"])
def api_save_client_id():
    global GOOGLE_CLIENT_ID
    data = request.get_json() or {}
    client_id = data.get("google_client_id", "").strip()
    if client_id:
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"google_client_id": client_id}, f)
            GOOGLE_CLIENT_ID = client_id
            return jsonify({"success": True, "message": "Client ID saved successfully."})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": False, "error": "Invalid client ID"}), 400

# ─────────────────────────────────────────────
# REST API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/kpi")
def api_kpi():
    total_alerts = sum(1 for v in VILLAGES for m in MEDICINES
                       if calculate_risk_level(
                           INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0),
                           get_daily_consumption(v["id"], m["id"])
                       )[0] in ["Critical", "High"])
    all_pcts = []
    for v in VILLAGES:
        inv = INVENTORY_DATA.get(v["id"], {})
        total = sum(inv.values())
        max_s = sum(get_daily_consumption(v["id"], m["id"]) * 30 for m in MEDICINES)
        all_pcts.append(min(100, round((total / max(max_s, 1)) * 100)))
    return jsonify({
        "villages_monitored": len(VILLAGES),
        "medicine_availability": round(sum(all_pcts) / len(all_pcts)),
        "active_alerts": total_alerts,
        "forecast_accuracy": 94,
        "outbreak_risk": round(len(DISEASE_OUTBREAKS) * 2.1, 1),
        "active_outbreaks": len(DISEASE_OUTBREAKS),
        "transport_vehicles": len([t for t in TRANSPORTATION if t["available"]]),
        "medicines_tracked": len(MEDICINES),
    })

@app.route("/api/demand-prediction")
def api_demand_prediction():
    period = request.args.get("days", "7")
    days = int(period)
    results = []
    for v in VILLAGES:
        for m in MEDICINES:
            stock = INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0)
            predicted = predict_demand(v["id"], m["id"], days)
            daily = get_daily_consumption(v["id"], m["id"])
            risk, days_rem = calculate_risk_level(stock, daily)
            results.append({
                "village": v["name"],
                "village_id": v["id"],
                "medicine": m["name"],
                "medicine_id": m["id"],
                "category": m["category"],
                "current_stock": stock,
                "predicted_demand": predicted,
                "days_remaining": days_rem,
                "risk": risk,
                "daily_consumption": daily,
                "outbreak_factor": round(get_outbreak_multiplier(v["id"]), 2),
                "weather_factor": round(get_weather_multiplier(v["id"]), 2),
            })
    results.sort(key=lambda x: ({"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(x["risk"], 4)))
    return jsonify({"predictions": results, "generated_at": datetime.now().isoformat(), "period_days": days})

@app.route("/api/shortage-alerts")
def api_shortage_alerts():
    alerts = []
    for v in VILLAGES:
        outbreak = next((d for d in DISEASE_OUTBREAKS if d["village_id"] == v["id"]), None)
        for m in MEDICINES:
            stock = INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"])
            risk, days_rem = calculate_risk_level(stock, daily)
            if risk in ["Critical", "High", "Medium"]:
                stockout_date = (datetime.now() + timedelta(days=days_rem)).strftime("%Y-%m-%d")
                alerts.append({
                    "village": v["name"],
                    "village_id": v["id"],
                    "district": v["district"],
                    "medicine": m["name"],
                    "category": m["category"],
                    "critical": m["critical"],
                    "current_stock": stock,
                    "daily_consumption": daily,
                    "days_remaining": days_rem,
                    "risk_level": risk,
                    "estimated_stockout": stockout_date,
                    "outbreak_linked": outbreak["disease"] if outbreak else None,
                    "weather_alert": WEATHER_DATA.get(v["id"], {}).get("alert"),
                    "action_required": f"Dispatch {max(0, predict_demand(v['id'], m['id'], 14) - stock)} units within {max(1, int(days_rem)-1)} days",
                })
    alerts.sort(key=lambda x: ({"Critical": 0, "High": 1, "Medium": 2}.get(x["risk_level"], 3), x["days_remaining"]))
    return jsonify({"alerts": alerts, "total": len(alerts), "critical": sum(1 for a in alerts if a["risk_level"] == "Critical"), "generated_at": datetime.now().isoformat()})

@app.route("/api/stock-transfers")
def api_stock_transfers():
    transfers = []
    for v in VILLAGES:
        for m in MEDICINES:
            stock = INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"])
            risk, days_rem = calculate_risk_level(stock, daily)
            if risk in ["Critical", "High"]:
                # Find best donor village
                best_donor = None
                best_surplus = 0
                for donor in VILLAGES:
                    if donor["id"] == v["id"]:
                        continue
                    donor_stock = INVENTORY_DATA.get(donor["id"], {}).get(m["id"], 0)
                    donor_daily = get_daily_consumption(donor["id"], m["id"])
                    donor_days = donor_stock / max(donor_daily, 1)
                    if donor_days > 20:
                        surplus = donor_stock - (donor_daily * 14)
                        if surplus > best_surplus:
                            best_surplus = surplus
                            best_donor = donor
                if best_donor:
                    qty = min(best_surplus, predict_demand(v["id"], m["id"], 14) - stock)
                    qty = max(0, round(qty))
                    if qty > 0:
                        transfers.append({
                            "source": best_donor["name"],
                            "source_id": best_donor["id"],
                            "destination": v["name"],
                            "destination_id": v["id"],
                            "medicine": m["name"],
                            "quantity": qty,
                            "priority": risk,
                            "reason": f"{v['name']} has only {days_rem} days of stock",
                            "transport_time": random.randint(2, 8),
                            "road_condition": WEATHER_DATA.get(v["id"], {}).get("road_condition", "Good"),
                        })
    transfers.sort(key=lambda x: ({"Critical": 0, "High": 1}.get(x["priority"], 2)))
    return jsonify({"transfers": transfers, "total": len(transfers), "generated_at": datetime.now().isoformat()})

@app.route("/api/delivery-schedule")
def api_delivery_schedule():
    schedule = []
    alerts_data = api_shortage_alerts().get_json()["alerts"][:8]
    vehicles = [t for t in TRANSPORTATION if t["available"]]
    for i, alert in enumerate(alerts_data):
        v_id = alert["village_id"]
        m_id = next((m["id"] for m in MEDICINES if m["name"] == alert["medicine"]), "M001")
        qty = predict_demand(v_id, m_id, 14) - alert["current_stock"]
        qty = max(50, round(qty))
        vehicle = vehicles[i % len(vehicles)]
        road = WEATHER_DATA.get(v_id, {}).get("road_condition", "Good")
        base_time = {"Good": 4, "Fair": 6, "Poor": 10, "Critical": 16}.get(road, 6)
        delivery_dt = datetime.now() + timedelta(hours=base_time + random.randint(0, 4))
        schedule.append({
            "schedule_id": f"SCH{i+1:03d}",
            "vehicle": vehicle["type"],
            "vehicle_id": vehicle["id"],
            "route": f"Central Hub → {alert['village']} PHC",
            "source": "Central Warehouse",
            "destination": alert["village"],
            "medicines": alert["medicine"],
            "quantity": qty,
            "delivery_time": delivery_dt.strftime("%Y-%m-%d %H:%M"),
            "priority": alert["risk_level"],
            "road_condition": road,
            "estimated_hours": base_time,
            "status": "Scheduled",
        })
    return jsonify({"schedule": schedule, "total": len(schedule), "generated_at": datetime.now().isoformat()})

@app.route("/api/emergency")
def api_emergency():
    critical_outbreaks = [d for d in DISEASE_OUTBREAKS if d["severity"] in ["Critical", "High"]]
    plans = []
    for outbreak in critical_outbreaks:
        v = next((v for v in VILLAGES if v["id"] == outbreak["village_id"]), None)
        if not v:
            continue
        critical_meds = [m for m in MEDICINES if m["critical"]]
        allocations = []
        for m in critical_meds:
            qty = predict_demand(v["id"], m["id"], 14)
            allocations.append({"medicine": m["name"], "quantity": qty, "category": m["category"]})
        best_vehicle = next((t for t in TRANSPORTATION if t["available"] and t["capacity"] >= 200), TRANSPORTATION[0])
        plans.append({
            "outbreak_id": outbreak["id"],
            "village": v["name"],
            "disease": outbreak["disease"],
            "affected_patients": outbreak["affected"],
            "severity": outbreak["severity"],
            "spread_rate": outbreak["spread_rate"],
            "critical_medicines": allocations,
            "recommended_vehicle": best_vehicle["type"],
            "transport_routes": [f"Central Hub → {v['name']} PHC (Primary)", f"Gulbarga Hub → {v['name']} (Backup)"],
            "estimated_response_hours": 6 if outbreak["severity"] == "Critical" else 12,
            "action": "IMMEDIATE DISPATCH" if outbreak["severity"] == "Critical" else "PRIORITY DISPATCH",
        })
    return jsonify({"plans": plans, "total_affected": sum(o["affected"] for o in critical_outbreaks), "generated_at": datetime.now().isoformat()})

@app.route("/api/inventory-audit")
def api_inventory_audit():
    audit = []
    for v in VILLAGES:
        village_audit = {"village": v["name"], "village_id": v["id"], "items": []}
        total_value = 0
        for m in MEDICINES:
            stock = INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"])
            risk, days_rem = calculate_risk_level(stock, daily)
            expiry_days = random.randint(30, 365)
            expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
            village_audit["items"].append({
                "medicine": m["name"],
                "medicine_id": m["id"],
                "category": m["category"],
                "stock": stock,
                "daily_consumption": daily,
                "days_remaining": days_rem,
                "expiry_date": expiry_date,
                "expiry_days": expiry_days,
                "status": risk,
                "reorder_point": daily * 7,
                "needs_reorder": stock <= daily * 7,
            })
            total_value += stock * random.randint(2, 50)
        village_audit["total_value_inr"] = total_value
        village_audit["critical_items"] = sum(1 for i in village_audit["items"] if i["status"] == "Critical")
        audit.append(village_audit)
    return jsonify({"audit": audit, "generated_at": datetime.now().isoformat()})

@app.route("/api/villages")
def api_villages():
    result = []
    for v in VILLAGES:
        outbreak = next((d for d in DISEASE_OUTBREAKS if d["village_id"] == v["id"]), None)
        inv = INVENTORY_DATA.get(v["id"], {})
        total_stock = sum(inv.values())
        max_stock = sum(get_daily_consumption(v["id"], m["id"]) * 30 for m in MEDICINES)
        avail_pct = min(100, round((total_stock / max(max_stock, 1)) * 100))
        alerts = sum(1 for m in MEDICINES if calculate_risk_level(inv.get(m["id"], 0), get_daily_consumption(v["id"], m["id"]))[0] in ["Critical", "High"])
        status = "critical" if alerts >= 3 else ("warning" if alerts >= 1 else "safe")
        result.append({**v, "availability_pct": avail_pct, "active_alerts": alerts,
                        "status": status, "outbreak": outbreak["disease"] if outbreak else None,
                        "weather": WEATHER_DATA.get(v["id"], {})})
    return jsonify(result)

@app.route("/api/raw/outbreaks")
def api_raw_outbreaks():
    return jsonify(DISEASE_OUTBREAKS)

@app.route("/api/raw/transport")
def api_raw_transport():
    return jsonify(TRANSPORTATION)

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json()
    village_name = data.get("village", "Unknown")
    population = int(data.get("population", 10000))
    fever_cases = int(data.get("fever_cases", 0))
    stock = int(data.get("stock", 500))
    usage = int(data.get("usage", 100))
    disease = data.get("disease", "Dengue")

    risk_score = min(10.0, round((fever_cases / max(population / 1000, 1)) * 1.5, 1))
    outbreak_prob = min(95, round((fever_cases / max(population / 100, 1)) * 1.8))
    predicted_demand = round(usage * (1 + fever_cases / max(population / 100, 1)))
    days_remaining = round(stock / max(usage / 7, 1))
    confidence = round(85 + random.uniform(0, 12), 1)
    dispatch_qty = max(0, predicted_demand * 2 - stock + 100)

    return jsonify({
        "village": village_name, "analyzed_at": datetime.now().isoformat(),
        "disease_agent": {"risk_score": risk_score, "outbreak_probability": outbreak_prob, "confidence": confidence, "disease": disease},
        "demand_agent": {"predicted_demand": predicted_demand, "forecast_7d": round(predicted_demand * 1.3), "forecast_30d": round(predicted_demand * 1.8), "trend": "Rising"},
        "inventory_agent": {"stock_health": "Critical" if days_remaining < 5 else ("Low" if days_remaining < 10 else "Moderate"), "shortage_probability": min(95, round(100 - days_remaining * 8)), "days_remaining": days_remaining, "expiry_risk": "Low"},
        "logistics_agent": {"recommended_dispatch": round(dispatch_qty), "delivery_eta_hours": random.randint(6, 24), "route_efficiency": round(75 + random.uniform(0, 20), 1)},
        "alert_agent": {"alert_level": "RED" if risk_score > 7 else ("ORANGE" if risk_score > 4 else "YELLOW"), "emergency_status": "ACTIVE" if risk_score > 7 else "STANDBY", "actions": max(2, round(risk_score))},
        "recommendation": f"Dispatch {round(dispatch_qty)} units of medicine to {village_name} within {'24 hours' if risk_score > 6 else '48 hours'}. Current risk level is {'CRITICAL' if risk_score > 7 else 'HIGH'}.",
    })

@app.route("/api/charts/demand-trend")
def api_demand_trend():
    labels = [(datetime.now() - timedelta(days=6-i)).strftime("%a") for i in range(7)]
    datasets = []
    for v in VILLAGES[:4]:
        data = [get_daily_consumption(v["id"], "M001") * round(get_outbreak_multiplier(v["id"]) * (0.9 + random.uniform(0, 0.3)), 2) for _ in range(7)]
        datasets.append({"label": v["name"], "data": [round(d) for d in data]})
    return jsonify({"labels": labels, "datasets": datasets})

@app.route("/api/charts/inventory-distribution")
def api_inventory_dist():
    statuses = {"Adequate": 0, "Low": 0, "Critical": 0, "Expiring Soon": 0}
    for v in VILLAGES:
        for m in MEDICINES:
            stock = INVENTORY_DATA.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"])
            risk, days = calculate_risk_level(stock, daily)
            if risk == "Critical": statuses["Critical"] += 1
            elif risk in ["High", "Medium"]: statuses["Low"] += 1
            else:
                if random.random() < 0.1: statuses["Expiring Soon"] += 1
                else: statuses["Adequate"] += 1
    return jsonify({"labels": list(statuses.keys()), "data": list(statuses.values())})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("DEBUG", "True").lower() == "true"
    print("\n" + "="*60)
    print("  MediReach AI v2 — Flask Backend")
    print(f"  URL: http://localhost:{port}")
    print(f"  API: http://localhost:{port}/api/kpi")
    print("="*60 + "\n")
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
