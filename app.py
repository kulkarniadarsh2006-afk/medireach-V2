"""
MediReach AI v2 — Flask Backend
AI-Powered Rural Healthcare Medicine Distribution Platform
Matches Pega Blueprint: 11 Personas | 8 Workflows | 14 Data Objects
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import random
import math
import threading
import time
import os
import urllib.request
import json
import ssl
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = "medireach_ai_2026"

# Load Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment or .env file.")

SUPABASE_URL = SUPABASE_URL.strip().rstrip('/')
SUPABASE_ANON_KEY = SUPABASE_ANON_KEY.strip()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

def safe_print(text):
    """Safely print text by encoding to ASCII and ignoring unicode characters that crash Windows terminals"""
    try:
        print(text.encode('ascii', 'ignore').decode('ascii'))
    except Exception:
        pass

# ─────────────────────────────────────────────
# DATABASE ACCESS HELPERS (NATIVE HTTP REST CLIENT)
# ─────────────────────────────────────────────

def supabase_request(endpoint, method="GET", data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req_data = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        safe_print(f"Supabase HTTP Request Error on {endpoint}: {e}")
        raise e

# Verify database connection on startup
try:
    # Test connection by querying a single PHC
    supabase_request("phcs?select=PHC_Code&limit=1")
    safe_print("Successfully connected to Supabase PostgreSQL Database via HTTP REST Client!")
except Exception as e:
    safe_print(f"Critical error: Supabase connection failed: {e}")
    raise RuntimeError(f"Failed to connect to Supabase database: {e}")

# ─────────────────────────────────────────────
# DYNAMIC CACHES & GENERATORS FOR NON-DB DATA
# ─────────────────────────────────────────────

WEATHER_CACHE = {}

def get_weather_for_phc(phc_id):
    if phc_id not in WEATHER_CACHE:
        # Deterministically initialize weather based on PHC code hash
        h = hash(phc_id)
        temp = 28 + (abs(h) % 12)
        # Rainfall between 0 and 80 mm
        rainfall = (abs(h * 3) % 80)
        humidity = 60 + (abs(h * 7) % 36)
        
        alert = None
        if rainfall > 60:
            alert = "Flood Risk"
            road_condition = "Critical"
        elif rainfall > 40:
            alert = "Heavy Rain"
            road_condition = "Poor"
        elif temp > 38:
            alert = "Heat Wave"
            road_condition = "Fair"
        else:
            road_condition = "Good" if rainfall < 15 else "Fair"
            
        WEATHER_CACHE[phc_id] = {
            "temp": temp,
            "rainfall": rainfall,
            "humidity": humidity,
            "alert": alert,
            "road_condition": road_condition
        }
    return WEATHER_CACHE[phc_id]

class WeatherDict(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = get_weather_for_phc(key)
        return super().__getitem__(key)
        
    def get(self, key, default=None):
        if key not in self:
            self[key] = get_weather_for_phc(key)
        return super().get(key, default)

WEATHER_DATA = WeatherDict()

VEHICLE_CACHE = []

def get_transportation_vehicles():
    global VEHICLE_CACHE
    if not VEHICLE_CACHE:
        # Generate vehicles dynamically
        vehicle_types = [
            ("Refrigerated Van", 500, "Nalgonda Depot"),
            ("Medical Truck", 1200, "Warangal Hub"),
            ("Motorcycle", 50, "Mahabubnagar Depot"),
            ("Medical Truck", 1200, "Nalgonda Depot"),
            ("Ambulance", 200, "Warangal Hub"),
            ("Drone Delivery", 10, "Central Hub")
        ]
        for idx, (v_type, cap, loc) in enumerate(vehicle_types):
            status = "Idle" if idx != 2 else "En Route"
            VEHICLE_CACHE.append({
                "id": f"T{idx+1:03d}",
                "type": v_type,
                "capacity": cap,
                "available": status in ["Idle", "En Route", "Ready"],
                "location": loc,
                "status": status
            })
    return VEHICLE_CACHE

TRANSPORTATION = get_transportation_vehicles()

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

def db_get_villages():
    try:
        rows = supabase_request("phcs?select=*")
        if not rows:
            return []
        villages = []
        for idx, r in enumerate(rows):
            code = r.get("PHC_Code") or r.get("code") or f"PHC-{idx:03d}"
            name = r.get("PHC_Name") or r.get("name") or f"PHC {idx}"
            pop = r.get("Population_Covered") or r.get("population") or 15000
            dist = r.get("District") or r.get("district") or "Unknown"
            
            h = hash(code)
            lat = 14.5 + abs(h % 300) / 100.0
            lng = 74.8 + abs((h // 3) % 400) / 100.0
            
            villages.append({
                "id": code,
                "name": name.replace("PHC ", "").replace("PHC", "").strip(),
                "population": int(pop),
                "district": dist,
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "phc": name if name.startswith("PHC") else f"PHC {name}",
                "growth_rate": 1.8,
                "age_distribution": {"0-14": 30, "15-60": 57, "60+": 13}
            })
        return villages
    except Exception as e:
        safe_print(f"Error fetching villages: {e}")
        return []

def db_get_medicines():
    try:
        rows = supabase_request("medicines?select=*")
        if not rows:
            return []
        return rows
    except Exception as e:
        safe_print(f"Error fetching medicines: {e}")
        return []

def db_get_inventory():
    try:
        rows = supabase_request("inventory?select=*")
        if not rows:
            return {}
        inv_data = {}
        for r in rows:
            phc = r.get("phc_code")
            med = r.get("medicine_id")
            stock = r.get("stock", 0)
            if phc not in inv_data:
                inv_data[phc] = {}
            inv_data[phc][med] = stock
        return inv_data
    except Exception as e:
        safe_print(f"Error fetching inventory: {e}")
        return {}

def db_get_outbreaks():
    try:
        rows = supabase_request("disease_outbreaks?select=*")
        if not rows:
            return []
        outbreaks = []
        for r in rows:
            outbreaks.append({
                "id": f"DO{r.get('id', 0):03d}",
                "village_id": r.get("phc_code"),
                "disease": r.get("disease"),
                "affected": r.get("affected", 0),
                "severity": r.get("severity", "Medium"),
                "spread_rate": r.get("spread_rate", 1.0),
                "started": str(r.get("started", "2026-06-01"))
            })
        return outbreaks
    except Exception as e:
        safe_print(f"Error fetching outbreaks: {e}")
        return []

def db_get_shortage_alerts():
    try:
        villages = db_get_villages()
        medicines = db_get_medicines()
        inventory = db_get_inventory()
        outbreaks = db_get_outbreaks()
        
        alerts = []
        alerts_to_sync = []
        for v in villages:
            outbreak = next((d for d in outbreaks if d["village_id"] == v["id"]), None)
            for m in medicines:
                stock = inventory.get(v["id"], {}).get(m["id"], 0)
                daily = get_daily_consumption(v["id"], m["id"], villages)
                risk, days_rem = calculate_risk_level(stock, daily)
                if risk in ["Critical", "High", "Medium"]:
                    stockout_date = (datetime.now() + timedelta(days=days_rem)).strftime("%Y-%m-%d")
                    action = f"Dispatch {max(0, predict_demand(v['id'], m['id'], 14, villages, outbreaks) - stock)} units within {max(1, int(days_rem)-1)} days"
                    
                    alert_item = {
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
                        "action_required": action
                    }
                    alerts.append(alert_item)
                    alerts_to_sync.append({
                        "phc_code": v["id"],
                        "medicine_id": m["id"],
                        "current_stock": stock,
                        "daily_consumption": daily,
                        "days_remaining": days_rem,
                        "risk_level": risk,
                        "estimated_stockout": stockout_date,
                        "action_required": action,
                        "outbreak_linked": outbreak["disease"] if outbreak else None,
                        "weather_alert": WEATHER_DATA.get(v["id"], {}).get("alert")
                    })
        
        if alerts_to_sync:
            try:
                # Clear and insert current alerts via REST DELETE and POST
                supabase_request("shortage_alerts?id=gt.0", method="DELETE")
                supabase_request("shortage_alerts", method="POST", data=alerts_to_sync[:100])
            except Exception as e:
                safe_print(f"Error syncing alerts: {e}")
                
        alerts.sort(key=lambda x: ({"Critical": 0, "High": 1, "Medium": 2}.get(x["risk_level"], 3), x["days_remaining"]))
        return alerts
    except Exception as e:
        safe_print(f"Error in dynamic shortage alert calculation: {e}")
        return []

def db_get_shipments():
    try:
        rows = supabase_request("logistics_shipments?select=*")
        if not rows:
            return []
        schedule = []
        villages = {v["id"]: v for v in db_get_villages()}
        medicines = {m["id"]: m for m in db_get_medicines()}
        for r in rows:
            dest_code = r.get("destination_phc_code")
            med_id = r.get("medicine_id")
            v_name = villages.get(dest_code, {}).get("name", dest_code)
            m_name = medicines.get(med_id, {}).get("name", med_id)
            
            dt_str = r.get("delivery_time", "")
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    dt_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            schedule.append({
                "schedule_id": r.get("id"),
                "vehicle": r.get("vehicle_type"),
                "vehicle_id": r.get("vehicle_id"),
                "route": r.get("route"),
                "source": "Central Warehouse",
                "destination": v_name,
                "medicines": m_name,
                "quantity": r.get("quantity", 0),
                "delivery_time": dt_str,
                "priority": r.get("priority", "Medium"),
                "road_condition": r.get("road_condition", "Good"),
                "estimated_hours": r.get("estimated_hours", 4),
                "status": r.get("status", "Scheduled")
            })
        return schedule
    except Exception as e:
        safe_print(f"Error fetching shipments: {e}")
        return []

# ─────────────────────────────────────────────
# AI ENGINE — PREDICTION LOGIC
# ─────────────────────────────────────────────

def get_daily_consumption(village_id, medicine_id, villages_list=None):
    """Calculate base daily consumption from population & historical data"""
    if villages_list is None:
        villages_list = db_get_villages()
    village = next((v for v in villages_list if v["id"] == village_id), None)
    if not village:
        return 0
    pop = village["population"]
    base_rates = {"M001": 0.015, "M002": 0.004, "M003": 0.006, "M004": 0.005,
                  "M005": 0.008, "M006": 0.007, "M007": 0.003, "M008": 0.002,
                  "M009": 0.002, "M010": 0.003}
    return round(pop * base_rates.get(medicine_id, 0.003))

def get_outbreak_multiplier(village_id, outbreaks_list=None):
    """Returns demand multiplier based on active outbreaks"""
    if outbreaks_list is None:
        outbreaks_list = db_get_outbreaks()
    outbreak = next((d for d in outbreaks_list if d["village_id"] == village_id), None)
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

def predict_demand(village_id, medicine_id, days, villages_list=None, outbreaks_list=None):
    """Core AI prediction engine"""
    if villages_list is None:
        villages_list = db_get_villages()
    if outbreaks_list is None:
        outbreaks_list = db_get_outbreaks()
    base = get_daily_consumption(village_id, medicine_id, villages_list)
    outbreak_mult = get_outbreak_multiplier(village_id, outbreaks_list)
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
# BACKGROUND SIMULATOR FOR LIVE WEBSOCKET DATA
# ─────────────────────────────────────────────

simulation_thread = None
thread_lock = threading.Lock()

def simulate_data_stream():
    """Simulates live database updates to medicine counts, outbreak severities, and weather conditions every 10 seconds."""
    time.sleep(5)  # Wait for server to fully initialize
    safe_print("WebSocket live update database-driven simulation thread started.")
    
    while True:
        try:
            time.sleep(10)
            
            # Select which type of update to simulate
            update_type = random.choice([0, 1, 2, 3])
            
            if update_type == 0:
                res = supabase_request("disease_outbreaks?select=*")
                outbreaks = res
                if outbreaks:
                    outbreak = random.choice(outbreaks)
                    delta = random.randint(1, 8)
                    new_affected = outbreak["affected"] + delta
                    
                    new_severity = outbreak["severity"]
                    if outbreak["severity"] == "Medium" and random.random() < 0.2:
                        new_severity = "High"
                    elif outbreak["severity"] == "High" and random.random() < 0.1:
                        new_severity = "Critical"
                        
                    try:
                        supabase_request(f"disease_outbreaks?id=eq.{outbreak['id']}", method="PATCH", data={
                            "affected": new_affected,
                            "severity": new_severity
                        })
                    except Exception as e:
                        safe_print(f"Warning: Could not write outbreak update to database: {e}")
                    
                    phc_res = supabase_request(f"phcs?PHC_Code=eq.{outbreak['phc_code']}&select=PHC_Name")
                    phc_name = phc_res[0]["PHC_Name"] if phc_res else outbreak["phc_code"]
                    
                    message = f"Outbreak Alert: Active {outbreak['disease']} cases in {phc_name} increased to {new_affected} ({new_severity} priority)."
                    socketio.emit("data_updated", {
                        "type": "outbreak",
                        "message": message,
                        "icon": "🦠"
                    })
                    safe_print(f"[WS DB EMIT] {message}")
                    
            elif update_type == 1:
                res = supabase_request("inventory?select=*")
                inv_items = res
                if inv_items:
                    item = random.choice(inv_items)
                    phc_code = item["phc_code"]
                    med_id = item["medicine_id"]
                    current_stock = item["stock"]
                    
                    phc_res = supabase_request(f"phcs?PHC_Code=eq.{phc_code}&select=PHC_Name")
                    phc_name = phc_res[0]["PHC_Name"] if phc_res else phc_code
                    med_res = supabase_request(f"medicines?id=eq.{med_id}&select=name")
                    med_name = med_res[0]["name"] if med_res else med_id
                    
                    if random.random() < 0.8:
                        drop = random.randint(15, 60)
                        new_stock = max(0, current_stock - drop)
                        try:
                            supabase_request(f"inventory?phc_code=eq.{phc_code}&medicine_id=eq.{med_id}", method="PATCH", data={"stock": new_stock})
                        except Exception as e:
                            safe_print(f"Warning: Could not write inventory drop to database: {e}")
                        message = f"Stock update: {med_name} inventory in {phc_name} dropped to {new_stock} units."
                        icon = "📉"
                    else:
                        refill = random.randint(100, 300)
                        new_stock = current_stock + refill
                        try:
                            supabase_request(f"inventory?phc_code=eq.{phc_code}&medicine_id=eq.{med_id}", method="PATCH", data={"stock": new_stock})
                        except Exception as e:
                            safe_print(f"Warning: Could not write inventory refill to database: {e}")
                        message = f"Supply Dispatch: Refilled {refill} units of {med_name} at {phc_name}."
                        icon = "🚚"
                        
                    socketio.emit("data_updated", {
                        "type": "inventory",
                        "message": message,
                        "icon": icon
                    })
                    safe_print(f"[WS DB EMIT] {message}")
                    
            elif update_type == 2:
                # Update weather
                villages = db_get_villages()
                if villages:
                    phc = random.choice(villages)
                    code = phc["id"]
                    name = phc["name"]
                    
                    weather = WEATHER_DATA[code]
                    temp_delta = random.choice([-2, -1, 1, 2])
                    weather["temp"] = max(10, min(50, weather["temp"] + temp_delta))
                    
                    if random.random() < 0.5:
                        weather["rainfall"] = max(0, weather["rainfall"] + random.randint(-5, 15))
                        if weather["rainfall"] > 50:
                            weather["alert"] = "Flood Risk"
                            weather["road_condition"] = "Critical"
                        elif weather["rainfall"] > 30:
                            weather["alert"] = "Heavy Rain"
                            weather["road_condition"] = "Poor"
                        else:
                            weather["alert"] = None
                            weather["road_condition"] = "Fair" if weather["rainfall"] > 10 else "Good"
                    
                    message = f"Weather Update: {name} is now {weather['temp']}°C with {weather['rainfall']}mm rain. Road is {weather['road_condition']}."
                    if weather["alert"]:
                        message += f" [ALERT: {weather['alert']}]"
                        
                    socketio.emit("data_updated", {
                        "type": "weather",
                        "message": message,
                        "icon": "🌤️"
                    })
                    safe_print(f"[WS DB EMIT] {message}")
                    
            elif update_type == 3 and TRANSPORTATION:
                vehicle = random.choice(TRANSPORTATION)
                old_status = vehicle["status"]
                
                status_choices = ["Idle", "En Route", "Ready", "Maintenance"]
                if old_status in status_choices:
                    status_choices.remove(old_status)
                new_status = random.choice(status_choices)
                
                vehicle["status"] = new_status
                vehicle["available"] = (new_status in ["Idle", "En Route", "Ready"])
                
                message = f"Logistics Alert: Vehicle {vehicle['id']} ({vehicle['type']}) changed status to {new_status}."
                socketio.emit("data_updated", {
                    "type": "logistics",
                    "message": message,
                    "icon": "🚛"
                })
                safe_print(f"[WS DB EMIT] {message}")
                
        except Exception as e:
            safe_print(f"Error in WebSocket simulation thread: {e}")
            time.sleep(5)

@socketio.on('connect')
def handle_connect():
    global simulation_thread
    with thread_lock:
        if simulation_thread is None:
            simulation_thread = threading.Thread(target=simulate_data_stream)
            simulation_thread.daemon = True
            simulation_thread.start()
    safe_print("Client browser connected via Socket.IO.")

# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    villages = db_get_villages()
    medicines = db_get_medicines()
    outbreaks = db_get_outbreaks()
    stats = {
        "villages": len(villages),
        "medicines": len(medicines),
        "outbreaks": len(outbreaks),
        "personas": len(PERSONAS),
        "workflows": 8,
        "data_objects": 14,
    }
    return render_template("index.html", stats=stats, personas=PERSONAS)

@app.route("/dashboard")
def dashboard():
    persona = request.args.get("persona", "PHC Administrator")
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    alerts = db_get_shortage_alerts()
    
    total_alerts = len([a for a in alerts if a["risk_level"] in ["Critical", "High"]])
    
    availability = []
    for v in villages:
        inv = inventory.get(v["id"], {})
        total_stock = sum(inv.values())
        max_stock = sum(get_daily_consumption(v["id"], m["id"], villages) * 30 for m in medicines)
        pct = min(100, round((total_stock / max(max_stock, 1)) * 100))
        availability.append({"village": v["name"], "pct": pct})
    
    avg_availability = round(sum(a["pct"] for a in availability) / len(availability)) if availability else 0
    active_outbreaks = len(outbreaks)
    
    return render_template("dashboard.html",
                           persona=persona, personas=PERSONAS,
                           villages=villages, medicines=medicines,
                           total_alerts=total_alerts,
                           avg_availability=avg_availability,
                           active_outbreaks=active_outbreaks,
                           outbreaks=outbreaks,
                           weather=WEATHER_DATA,
                           inventory=inventory)

@app.route("/demand")
def demand_page():
    return render_template("demand.html", villages=db_get_villages(), medicines=db_get_medicines(), personas=PERSONAS)

@app.route("/shortage")
def shortage_page():
    return render_template("shortage.html", villages=db_get_villages(), medicines=db_get_medicines(), personas=PERSONAS)

@app.route("/transfers")
def transfers_page():
    return render_template("transfers.html", villages=db_get_villages(), medicines=db_get_medicines(), personas=PERSONAS)

@app.route("/schedule")
def schedule_page():
    return render_template("schedule.html", villages=db_get_villages(), medicines=db_get_medicines(),
                           transport=TRANSPORTATION, personas=PERSONAS)

@app.route("/emergency")
def emergency_page():
    return render_template("emergency.html", villages=db_get_villages(), medicines=db_get_medicines(),
                           outbreaks=db_get_outbreaks(), personas=PERSONAS)

@app.route("/inventory-audit")
def inventory_audit_page():
    return render_template("inventory.html", villages=db_get_villages(), medicines=db_get_medicines(),
                           inventory=db_get_inventory(), personas=PERSONAS)

@app.route("/analytics")
def analytics_page():
    return render_template("analytics.html", villages=db_get_villages(), medicines=db_get_medicines(), personas=PERSONAS)

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

@app.route("/api/auth/switch-role", methods=["POST"])
def api_auth_switch_role():
    data = request.get_json() or {}
    role = data.get("role", "").strip()
    if role and "user" in session:
        session["user"]["role"] = role
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid role or user not logged in"}), 400

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

# ─────────────────────────────────────────────
# REST API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/kpi")
def api_kpi():
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    alerts = db_get_shortage_alerts()
    
    total_alerts = len([a for a in alerts if a["risk_level"] in ["Critical", "High"]])
    
    all_pcts = []
    for v in villages:
        inv = inventory.get(v["id"], {})
        total = sum(inv.values())
        max_s = sum(get_daily_consumption(v["id"], m["id"], villages) * 30 for m in medicines)
        all_pcts.append(min(100, round((total / max(max_s, 1)) * 100)))
        
    shipments = db_get_shipments()
    available_transport = len([t for t in TRANSPORTATION if t["available"]])
    
    return jsonify({
        "villages_monitored": len(villages),
        "medicine_availability": round(sum(all_pcts) / len(all_pcts)) if all_pcts else 0,
        "active_alerts": total_alerts,
        "forecast_accuracy": 94,
        "outbreak_risk": round(len(outbreaks) * 2.1, 1),
        "active_outbreaks": len(outbreaks),
        "transport_vehicles": available_transport,
        "medicines_tracked": len(medicines),
    })

@app.route("/api/demand-prediction")
def api_demand_prediction():
    period = request.args.get("days", "7")
    days = int(period)
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    
    results = []
    for v in villages:
        for m in medicines:
            stock = inventory.get(v["id"], {}).get(m["id"], 0)
            predicted = predict_demand(v["id"], m["id"], days, villages, outbreaks)
            daily = get_daily_consumption(v["id"], m["id"], villages)
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
                "outbreak_factor": round(get_outbreak_multiplier(v["id"], outbreaks), 2),
                "weather_factor": round(get_weather_multiplier(v["id"]), 2),
            })
    results.sort(key=lambda x: ({"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(x["risk"], 4)))
    return jsonify({"predictions": results, "generated_at": datetime.now().isoformat(), "period_days": days})

@app.route("/api/shortage-alerts")
def api_shortage_alerts():
    alerts = db_get_shortage_alerts()
    return jsonify({
        "alerts": alerts,
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["risk_level"] == "Critical"),
        "generated_at": datetime.now().isoformat()
    })

@app.route("/api/stock-transfers")
def api_stock_transfers():
    transfers = []
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    alerts = db_get_shortage_alerts()
    
    critical_alerts = [a for a in alerts if a["risk_level"] in ["Critical", "High"]]
    
    for alert in critical_alerts:
        v_id = alert["village_id"]
        m_name = alert["medicine"]
        med = next((m for m in medicines if m["name"] == m_name), None)
        if not med:
            continue
            
        stock = alert["current_stock"]
        daily = alert["daily_consumption"]
        days_rem = alert["days_remaining"]
        
        best_donor = None
        best_surplus = 0
        for donor in villages:
            if donor["id"] == v_id:
                continue
            donor_stock = inventory.get(donor["id"], {}).get(med["id"], 0)
            donor_daily = get_daily_consumption(donor["id"], med["id"], villages)
            donor_days = donor_stock / max(donor_daily, 1)
            if donor_days > 20:
                surplus = donor_stock - (donor_daily * 14)
                if surplus > best_surplus:
                    best_surplus = surplus
                    best_donor = donor
                    
        if best_donor:
            qty = min(best_surplus, predict_demand(v_id, med["id"], 14, villages, outbreaks) - stock)
            qty = max(0, round(qty))
            if qty > 0:
                transfers.append({
                    "source": best_donor["name"],
                    "source_id": best_donor["id"],
                    "destination": alert["village"],
                    "destination_id": v_id,
                    "medicine": med["name"],
                    "quantity": qty,
                    "priority": alert["risk_level"],
                    "reason": f"{alert['village']} has only {days_rem} days of stock",
                    "transport_time": random.randint(2, 8),
                    "road_condition": WEATHER_DATA.get(v_id, {}).get("road_condition", "Good"),
                })
    transfers.sort(key=lambda x: ({"Critical": 0, "High": 1}.get(x["priority"], 2)))
    return jsonify({"transfers": transfers, "total": len(transfers), "generated_at": datetime.now().isoformat()})

@app.route("/api/delivery-schedule")
def api_delivery_schedule():
    schedule = db_get_shipments()
    return jsonify({"schedule": schedule, "total": len(schedule), "generated_at": datetime.now().isoformat()})

@app.route("/api/emergency")
def api_emergency():
    outbreaks = db_get_outbreaks()
    villages = db_get_villages()
    medicines = db_get_medicines()
    
    critical_outbreaks = [d for d in outbreaks if d["severity"] in ["Critical", "High"]]
    plans = []
    for outbreak in critical_outbreaks:
        v = next((v for v in villages if v["id"] == outbreak["village_id"]), None)
        if not v:
            continue
        critical_meds = [m for m in medicines if m["critical"]]
        allocations = []
        for m in critical_meds:
            qty = predict_demand(v["id"], m["id"], 14, villages, outbreaks)
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
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    
    audit = []
    for v in villages:
        village_audit = {"village": v["name"], "village_id": v["id"], "items": []}
        total_value = 0
        for m in medicines:
            stock = inventory.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"], villages)
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
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    
    result = []
    for v in villages:
        outbreak = next((d for d in outbreaks if d["village_id"] == v["id"]), None)
        inv = inventory.get(v["id"], {})
        total_stock = sum(inv.values())
        max_stock = sum(get_daily_consumption(v["id"], m["id"], villages) * 30 for m in medicines)
        avail_pct = min(100, round((total_stock / max(max_stock, 1)) * 100))
        
        alerts = 0
        for m in medicines:
            stock = inv.get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"], villages)
            risk, _ = calculate_risk_level(stock, daily)
            if risk in ["Critical", "High"]:
                alerts += 1
        status = "critical" if alerts >= 3 else ("warning" if alerts >= 1 else "safe")
        result.append({**v, "availability_pct": avail_pct, "active_alerts": alerts,
                        "status": status, "outbreak": outbreak["disease"] if outbreak else None,
                        "weather": WEATHER_DATA.get(v["id"], {})})
    return jsonify(result)

@app.route("/api/raw/outbreaks")
def api_raw_outbreaks():
    return jsonify(db_get_outbreaks())

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
    villages = db_get_villages()
    outbreaks = db_get_outbreaks()
    for v in villages[:4]:
        data = [get_daily_consumption(v["id"], "M001", villages) * round(get_outbreak_multiplier(v["id"], outbreaks) * (0.9 + random.uniform(0, 0.3)), 2) for _ in range(7)]
        datasets.append({"label": v["name"], "data": [round(d) for d in data]})
    return jsonify({"labels": labels, "datasets": datasets})

@app.route("/api/charts/inventory-distribution")
def api_inventory_dist():
    statuses = {"Adequate": 0, "Low": 0, "Critical": 0, "Expiring Soon": 0}
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    for v in villages:
        for m in medicines:
            stock = inventory.get(v["id"], {}).get(m["id"], 0)
            daily = get_daily_consumption(v["id"], m["id"], villages)
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
    socketio.run(app, debug=debug_mode, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
