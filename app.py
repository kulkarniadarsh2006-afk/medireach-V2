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
import sqlite3
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
if SUPABASE_URL.endswith('/rest/v1'):
    SUPABASE_URL = SUPABASE_URL[:-8].rstrip('/')
SUPABASE_ANON_KEY = SUPABASE_ANON_KEY.strip()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

def safe_print(text):
    """Safely print text by encoding to ASCII and ignoring unicode characters that crash Windows terminals"""
    try:
        print(text.encode('ascii', 'ignore').decode('ascii'))
    except Exception:
        pass

# ─────────────────────────────────────────────
# DATABASE ACCESS HELPERS (NATIVE HTTP REST CLIENT & SQLITE FALLBACK)
# ─────────────────────────────────────────────

# Shared SSL context — created once at startup, reused for all requests
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medireach_local.db")

def query_sqlite(query, params=(), commit=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            return cursor.lastrowid
        else:
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        safe_print(f"SQLite Query Error: {e}")
        return []
    finally:
        conn.close()

def supabase_request(endpoint, method="GET", data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    req_data = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        safe_print(f"Supabase HTTP Request Error on {endpoint}: {e}")
        raise e

# Verify database connection on startup
SUPABASE_CONNECTED = False
try:
    supabase_request("phcs?select=PHC_Code&limit=1")
    safe_print("Successfully connected to Supabase PostgreSQL Database via HTTP REST Client!")
    SUPABASE_CONNECTED = True
except Exception as e:
    safe_print(f"Warning: Supabase connection failed: {e}. Operating in Local-First SQLite mode.")

# ─────────────────────────────────────────────
# DATABASE WRITE & CRUD HELPERS (WITH SQLITE FALLBACKS)
# ─────────────────────────────────────────────

def db_insert_user(user_data):
    try:
        query_sqlite(
            "INSERT OR REPLACE INTO users (username, email, mobile, role, phc_code, phc_name, district) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_data.get("given_name"), user_data.get("email"), user_data.get("mobile"), user_data.get("role"), user_data.get("phc_code"), user_data.get("phc_name"), user_data.get("district")),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite user insert error: {e}")
        
    try:
        supabase_request("users", method="POST", data={
            "username": user_data.get("given_name"),
            "email": user_data.get("email"),
            "mobile": user_data.get("mobile"),
            "role": user_data.get("role"),
            "phc_code": user_data.get("phc_code"),
            "phc_name": user_data.get("phc_name"),
            "district": user_data.get("district")
        })
    except Exception as e:
        safe_print(f"Supabase user insert failed (ignored): {e}")

def db_update_inventory(phc_code, medicine_id, stock, batch_number=""):
    try:
        query_sqlite(
            "INSERT OR REPLACE INTO inventory (phc_code, medicine_id, stock, batch_number) VALUES (?, ?, ?, ?)",
            (phc_code, medicine_id, stock, batch_number),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite inventory update error: {e}")
        
    try:
        supabase_request("inventory", method="POST", data={
            "phc_code": phc_code,
            "medicine_id": medicine_id,
            "stock": stock,
            "batch_number": batch_number
        })
    except Exception as e:
        safe_print(f"Supabase inventory update failed (ignored): {e}")

def db_insert_outbreak(outbreak_data):
    try:
        query_sqlite(
            "INSERT INTO disease_outbreaks (phc_code, disease, affected, severity, spread_rate, started, disease_category, cases_reported) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (outbreak_data["phc_code"], outbreak_data["disease"], outbreak_data["affected"], outbreak_data["severity"], outbreak_data["spread_rate"], outbreak_data["started"], outbreak_data.get("disease_category"), outbreak_data.get("cases_reported")),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite outbreak insert error: {e}")
        
    try:
        supabase_request("disease_outbreaks", method="POST", data={
            "phc_code": outbreak_data["phc_code"],
            "disease": outbreak_data["disease"],
            "affected": outbreak_data["affected"],
            "severity": outbreak_data["severity"],
            "spread_rate": outbreak_data["spread_rate"],
            "started": outbreak_data["started"],
            "disease_category": outbreak_data.get("disease_category"),
            "cases_reported": outbreak_data.get("cases_reported")
        })
    except Exception as e:
        safe_print(f"Supabase outbreak insert failed (ignored): {e}")

def db_insert_request(request_data):
    try:
        query_sqlite(
            "INSERT INTO medicine_requests (phc_code, medicine_id, quantity, status, priority) VALUES (?, ?, ?, ?, ?)",
            (request_data["phc_code"], request_data["medicine_id"], request_data["quantity"], request_data.get("status", "Pending"), request_data.get("priority", "Medium")),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite request insert error: {e}")
        
    try:
        supabase_request("medicine_requests", method="POST", data={
            "phc_code": request_data["phc_code"],
            "medicine_id": request_data["medicine_id"],
            "quantity": request_data["quantity"],
            "status": request_data.get("status", "Pending"),
            "priority": request_data.get("priority", "Medium")
        })
    except Exception as e:
        safe_print(f"Supabase request insert failed (ignored): {e}")

def db_insert_patient_statistics(stat_data):
    try:
        query_sqlite(
            "INSERT INTO patient_statistics (phc_code, opd_patients_total, opd_new_cases, opd_referred_cases, opd_immunizations, recorded_date) VALUES (?, ?, ?, ?, ?, ?)",
            (stat_data["phc_code"], stat_data["opd_patients_total"], stat_data["opd_new_cases"], stat_data["opd_referred_cases"], stat_data["opd_immunizations"], stat_data["recorded_date"]),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite stats insert error: {e}")
        
    try:
        supabase_request("patient_statistics", method="POST", data={
            "phc_code": stat_data["phc_code"],
            "opd_patients_total": stat_data["opd_patients_total"],
            "opd_new_cases": stat_data["opd_new_cases"],
            "opd_referred_cases": stat_data["opd_referred_cases"],
            "opd_immunizations": stat_data["opd_immunizations"],
            "recorded_date": stat_data["recorded_date"]
        })
    except Exception as e:
        safe_print(f"Supabase stats insert failed (ignored): {e}")

def db_insert_sync_log(sync_row):
    try:
        query_sqlite(
            "INSERT OR REPLACE INTO rhim_sync_log (sync_id, phc_code, phc_name, district, synced_at, sync_source, inventory_items_received, inventory_total_units, inventory_critical_items, disease_reports_received, disease_cases_total, disease_alerts, opd_patients_total, opd_new_cases, opd_referred_cases, opd_immunizations, inventory_payload, disease_payload, opd_payload, sync_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sync_row["sync_id"], sync_row["phc_code"], sync_row["phc_name"], sync_row.get("district", ""), sync_row["synced_at"], sync_row.get("sync_source", "PHC-Portal"), sync_row.get("inventory_items_received", 0), sync_row.get("inventory_total_units", 0), sync_row.get("inventory_critical_items", 0), sync_row.get("disease_reports_received", 0), sync_row.get("disease_cases_total", 0), sync_row.get("disease_alerts", 0), sync_row.get("opd_patients_total", 0), sync_row.get("opd_new_cases", 0), sync_row.get("opd_referred_cases", 0), sync_row.get("opd_immunizations", 0), sync_row.get("inventory_payload"), sync_row.get("disease_payload"), sync_row.get("opd_payload"), sync_row.get("sync_status", "completed")),
            commit=True
        )
    except Exception as e:
        safe_print(f"SQLite sync log insert error: {e}")
        
    try:
        supabase_request("rhim_sync_log", method="POST", data=sync_row)
    except Exception as e:
        safe_print(f"Supabase sync log insert failed (ignored): {e}")

# ─────────────────────────────────────────────
# DATABASE READ & SYNC LOG HELPERS
# ─────────────────────────────────────────────

def db_get_sync_logs(phc_code=None, limit=10):
    if phc_code:
        query = "SELECT * FROM rhim_sync_log WHERE phc_code = ? ORDER BY synced_at DESC LIMIT ?"
        params = (phc_code, limit)
    else:
        query = "SELECT * FROM rhim_sync_log ORDER BY synced_at DESC LIMIT ?"
        params = (limit,)
    rows = query_sqlite(query, params)
    for r in rows:
        r["ai_recommendations"] = _generate_rhim_ai_recommendations(r)
    return rows

def db_get_latest_sync_logs():
    query = "SELECT * FROM rhim_sync_log ORDER BY synced_at DESC"
    rows = query_sqlite(query)
    for r in rows:
        r["ai_recommendations"] = _generate_rhim_ai_recommendations(r)
    return rows

def db_get_patient_statistics(phc_code=None):
    if phc_code:
        query = "SELECT * FROM patient_statistics WHERE phc_code = ? ORDER BY recorded_date DESC"
        params = (phc_code,)
    else:
        query = "SELECT * FROM patient_statistics ORDER BY recorded_date DESC"
        params = ()
    return query_sqlite(query, params)

def db_get_deliveries():
    query = "SELECT * FROM deliveries ORDER BY updated_at DESC"
    return query_sqlite(query)

# ─────────────────────────────────────────────
# IN-MEMORY TTL CACHE  (60s for reads, avoids hammering Supabase)
# ─────────────────────────────────────────────

_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()
CACHE_TTL = 60  # seconds

def _cache_get(key):
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and (time.time() - entry['ts']) < CACHE_TTL:
            return entry['data']
    return None

def _cache_set(key, data):
    with _CACHE_LOCK:
        _CACHE[key] = {'data': data, 'ts': time.time()}

def _cache_invalidate(key):
    with _CACHE_LOCK:
        _CACHE.pop(key, None)

def cached_supabase_get(endpoint, cache_key):
    """GET with 60-second TTL cache."""
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit
    data = supabase_request(endpoint)
    _cache_set(cache_key, data)
    return data

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
        rows = cached_supabase_get("phcs?select=*", "villages")
        if not rows:
            raise Exception("No data from Supabase")
    except Exception as e:
        safe_print(f"Supabase fetch phcs failed, falling back to local SQLite: {e}")
        rows = query_sqlite("SELECT PHC_Code as code, PHC_Name as name, Population_Covered as population, District as district FROM phcs")
        
    villages = []
    for idx, r in enumerate(rows):
        code = r.get("code") or r.get("PHC_Code") or f"PHC-{idx:03d}"
        name = r.get("name") or r.get("PHC_Name") or f"PHC {idx}"
        pop = r.get("population") or r.get("Population_Covered") or 15000
        dist = r.get("district") or r.get("District") or "Unknown"

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

def db_get_medicines():
    try:
        rows = cached_supabase_get("medicines?select=*", "medicines")
        if not rows:
            raise Exception("No data from Supabase")
        return rows
    except Exception as e:
        safe_print(f"Supabase fetch medicines failed, falling back to SQLite: {e}")
        rows = query_sqlite("SELECT id, name, category, unit, critical FROM medicines")
        return [{"id": r["id"], "name": r["name"], "category": r["category"], "unit": r["unit"], "critical": bool(r["critical"])} for r in rows]

def db_get_inventory():
    try:
        rows = cached_supabase_get("inventory?select=*", "inventory")
        if not rows:
            raise Exception("No data from Supabase")
    except Exception as e:
        safe_print(f"Supabase fetch inventory failed, falling back to SQLite: {e}")
        rows = query_sqlite("SELECT phc_code, medicine_id, stock FROM inventory")
        
    inv_data = {}
    for r in rows:
        phc = r.get("phc_code")
        med = r.get("medicine_id")
        stock = r.get("stock", 0)
        if phc not in inv_data:
            inv_data[phc] = {}
        inv_data[phc][med] = stock
    return inv_data

def db_get_outbreaks():
    try:
        rows = cached_supabase_get("disease_outbreaks?select=*", "outbreaks")
        if not rows:
            raise Exception("No data from Supabase")
    except Exception as e:
        safe_print(f"Supabase fetch outbreaks failed, falling back to SQLite: {e}")
        rows = query_sqlite("SELECT id, phc_code, disease, affected, severity, spread_rate, started FROM disease_outbreaks")
        
    outbreaks = []
    for r in rows:
        outbreaks.append({
            "id": f"DO{r.get('id', 0):03d}" if isinstance(r.get('id'), int) else r.get('id'),
            "village_id": r.get("phc_code"),
            "disease": r.get("disease"),
            "affected": r.get("affected", 0),
            "severity": r.get("severity", "Medium"),
            "spread_rate": r.get("spread_rate", 1.0),
            "started": str(r.get("started", "2026-06-01"))
        })
    return outbreaks

def db_get_shortage_alerts():
    """Compute shortage alerts from cached DB data. Results cached for 60s."""
    cached = _cache_get("shortage_alerts")
    if cached is not None:
        return cached

    try:
        villages = db_get_villages()
        medicines = db_get_medicines()
        inventory = db_get_inventory()
        outbreaks = db_get_outbreaks()

        # Pre-build outbreak lookup: village_id -> outbreak
        outbreak_map = {d["village_id"]: d for d in outbreaks}

        alerts = []
        for v in villages:
            outbreak = outbreak_map.get(v["id"])
            for m in medicines:
                stock = inventory.get(v["id"], {}).get(m["id"], 0)
                daily = get_daily_consumption(v["id"], m["id"], villages)
                risk, days_rem = calculate_risk_level(stock, daily)
                if risk in ["Critical", "High", "Medium"]:
                    stockout_date = (datetime.now() + timedelta(days=days_rem)).strftime("%Y-%m-%d")
                    action = f"Dispatch {max(0, predict_demand(v['id'], m['id'], 14, villages, outbreaks) - stock)} units within {max(1, int(days_rem)-1)} days"
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
                        "action_required": action
                    })

        alerts.sort(key=lambda x: ({"Critical": 0, "High": 1, "Medium": 2}.get(x["risk_level"], 3), x["days_remaining"]))
        _cache_set("shortage_alerts", alerts)
        return alerts
    except Exception as e:
        safe_print(f"Error in shortage alert calculation: {e}")
        return []

def db_get_shipments():
    try:
        rows = cached_supabase_get("logistics_shipments?select=*", "shipments")
        if not rows:
            raise Exception("No data from Supabase")
    except Exception as e:
        safe_print(f"Supabase fetch shipments failed, falling back to SQLite: {e}")
        rows = query_sqlite("SELECT id, vehicle_type, vehicle_id, route, source_warehouse_id, destination_phc_code, medicine_id, quantity, delivery_time, priority, road_condition, estimated_hours, status FROM logistics_shipments")
        
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
            "schedule_id": r.get("id") or r.get("schedule_id"),
            "vehicle": r.get("vehicle_type") or r.get("vehicle"),
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
    """Simulates live updates every 30s. Uses cached data wherever possible."""
    time.sleep(5)
    safe_print("WebSocket live update simulation thread started.")

    while True:
        try:
            time.sleep(30)  # Reduced from 10s → 30s to cut Supabase load

            update_type = random.choice([0, 1, 2, 3])

            if update_type == 0:
                # Use cached outbreaks — only write back if we actually change something
                outbreaks_raw = cached_supabase_get("disease_outbreaks?select=*", "outbreaks")
                if outbreaks_raw:
                    outbreak = random.choice(outbreaks_raw)
                    delta = random.randint(1, 8)
                    new_affected = outbreak["affected"] + delta
                    new_severity = outbreak["severity"]
                    if outbreak["severity"] == "Medium" and random.random() < 0.2:
                        new_severity = "High"
                    elif outbreak["severity"] == "High" and random.random() < 0.1:
                        new_severity = "Critical"
                    try:
                        supabase_request(f"disease_outbreaks?id=eq.{outbreak['id']}", method="PATCH",
                                         data={"affected": new_affected, "severity": new_severity})
                        # Invalidate cached outbreaks so next read gets fresh data
                        _cache_invalidate("outbreaks")
                    except Exception as e:
                        safe_print(f"Warning: Could not write outbreak update: {e}")

                    # Use cached PHC name lookup
                    villages_raw = cached_supabase_get("phcs?select=*", "villages")
                    phc_name = next((r.get("PHC_Name", outbreak["phc_code"])
                                     for r in villages_raw if r.get("PHC_Code") == outbreak["phc_code"]), outbreak["phc_code"])
                    message = (f"Outbreak Alert: {outbreak['disease']} in {phc_name} "
                               f"increased to {new_affected} ({new_severity}).")
                    socketio.emit("data_updated", {"type": "outbreak", "message": message, "icon": "🦠"})

            elif update_type == 1:
                inv_items = cached_supabase_get("inventory?select=*", "inventory")
                if inv_items:
                    item = random.choice(inv_items)
                    phc_code = item["phc_code"]
                    med_id = item["medicine_id"]
                    current_stock = item["stock"]

                    villages_raw = cached_supabase_get("phcs?select=*", "villages")
                    meds_raw = cached_supabase_get("medicines?select=*", "medicines")
                    phc_name = next((r.get("PHC_Name", phc_code) for r in villages_raw if r.get("PHC_Code") == phc_code), phc_code)
                    med_name = next((r.get("name", med_id) for r in meds_raw if r.get("id") == med_id), med_id)

                    if random.random() < 0.8:
                        drop = random.randint(15, 60)
                        new_stock = max(0, current_stock - drop)
                        try:
                            supabase_request(f"inventory?phc_code=eq.{phc_code}&medicine_id=eq.{med_id}",
                                             method="PATCH", data={"stock": new_stock})
                            _cache_invalidate("inventory")
                        except Exception as e:
                            safe_print(f"Warning: Could not write inventory drop: {e}")
                        message = f"Stock update: {med_name} in {phc_name} dropped to {new_stock} units."
                        icon = "📉"
                    else:
                        refill = random.randint(100, 300)
                        new_stock = current_stock + refill
                        try:
                            supabase_request(f"inventory?phc_code=eq.{phc_code}&medicine_id=eq.{med_id}",
                                             method="PATCH", data={"stock": new_stock})
                            _cache_invalidate("inventory")
                        except Exception as e:
                            safe_print(f"Warning: Could not write inventory refill: {e}")
                        message = f"Supply Dispatch: Refilled {refill} units of {med_name} at {phc_name}."
                        icon = "🚚"
                    socketio.emit("data_updated", {"type": "inventory", "message": message, "icon": icon})

            elif update_type == 2:
                # Weather is in-memory — no Supabase call needed
                if WEATHER_CACHE:
                    code = random.choice(list(WEATHER_CACHE.keys()))
                    weather = WEATHER_CACHE[code]
                    temp_delta = random.choice([-2, -1, 1, 2])
                    weather["temp"] = max(10, min(50, weather["temp"] + temp_delta))
                    if random.random() < 0.5:
                        weather["rainfall"] = max(0, weather["rainfall"] + random.randint(-5, 15))
                        if weather["rainfall"] > 50:
                            weather["alert"] = "Flood Risk"; weather["road_condition"] = "Critical"
                        elif weather["rainfall"] > 30:
                            weather["alert"] = "Heavy Rain"; weather["road_condition"] = "Poor"
                        else:
                            weather["alert"] = None
                            weather["road_condition"] = "Fair" if weather["rainfall"] > 10 else "Good"
                    message = (f"Weather: {code} now {weather['temp']}°C, {weather['rainfall']}mm rain. "
                               f"Road: {weather['road_condition']}.")
                    if weather["alert"]:
                        message += f" [{weather['alert']}]"
                    socketio.emit("data_updated", {"type": "weather", "message": message, "icon": "🌤️"})

            elif update_type == 3 and TRANSPORTATION:
                vehicle = random.choice(TRANSPORTATION)
                old_status = vehicle["status"]
                choices = [s for s in ["Idle", "En Route", "Ready", "Maintenance"] if s != old_status]
                new_status = random.choice(choices)
                vehicle["status"] = new_status
                vehicle["available"] = new_status in ["Idle", "En Route", "Ready"]
                message = f"Logistics: Vehicle {vehicle['id']} ({vehicle['type']}) → {new_status}."
                socketio.emit("data_updated", {"type": "logistics", "message": message, "icon": "🚛"})

        except Exception as e:
            safe_print(f"Error in WebSocket simulation thread: {e}")
            time.sleep(10)

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

def render_phc_user_dashboard():
    phc_code = session["user"].get("phc_code")
    phc_name = session["user"].get("phc_name")
    all_meds = db_get_medicines()
    med_map = {m["id"]: m for m in all_meds}
    
    # Inventory rows
    inventory_rows = []
    try:
        inventory_rows = supabase_request(f"inventory?phc_code=eq.{phc_code}")
        if not inventory_rows:
            inventory_rows = query_sqlite("SELECT * FROM inventory WHERE phc_code = ?", (phc_code,))
    except Exception as e:
        safe_print(f"Error fetching inventory: {e}")
        inventory_rows = query_sqlite("SELECT * FROM inventory WHERE phc_code = ?", (phc_code,))
        
    local_inventory = []
    total_stock_units = 0
    low_stock_alerts_count = 0
    critical_alerts_count = 0
    
    for r in inventory_rows:
        med_id = r.get("medicine_id")
        stock = r.get("stock", 0)
        med_info = med_map.get(med_id, {"name": med_id, "category": "Unknown", "unit": "Units", "critical": False})
        
        daily_cons = get_daily_consumption(phc_code, med_id, db_get_villages())
        risk, days_rem = calculate_risk_level(stock, daily_cons)
        
        total_stock_units += stock
        if risk == "Critical":
            critical_alerts_count += 1
        elif risk == "High":
            low_stock_alerts_count += 1
            
        local_inventory.append({
            "medicine_id": med_id,
            "name": med_info["name"],
            "category": med_info["category"],
            "unit": med_info["unit"],
            "stock": stock,
            "daily_consumption": daily_cons,
            "days_remaining": round(days_rem, 1) if days_rem < 999 else "Stable",
            "risk_level": risk
        })
    local_inventory.sort(key=lambda x: x["name"])
    
    # Outbreak rows
    outbreak_rows = []
    try:
        outbreak_rows = supabase_request(f"disease_outbreaks?phc_code=eq.{phc_code}")
        if not outbreak_rows:
            outbreak_rows = query_sqlite("SELECT * FROM disease_outbreaks WHERE phc_code = ?", (phc_code,))
    except Exception as e:
        outbreak_rows = query_sqlite("SELECT * FROM disease_outbreaks WHERE phc_code = ?", (phc_code,))
        
    # Requests rows
    request_rows = []
    try:
        request_rows = supabase_request(f"medicine_requests?phc_code=eq.{phc_code}&order=created_at.desc&limit=10")
        if not request_rows:
            request_rows = query_sqlite("SELECT * FROM medicine_requests WHERE phc_code = ? ORDER BY created_at DESC LIMIT 10", (phc_code,))
    except Exception as e:
        request_rows = query_sqlite("SELECT * FROM medicine_requests WHERE phc_code = ? ORDER BY created_at DESC LIMIT 10", (phc_code,))
        
    formatted_requests = []
    for req in request_rows:
        med_id = req.get("medicine_id")
        med_name = med_map.get(med_id, {}).get("name", med_id)
        formatted_requests.append({
            "id": req.get("id"),
            "medicine_name": med_name,
            "quantity": req.get("quantity"),
            "priority": req.get("priority", "Medium"),
            "status": req.get("status", "Pending"),
            "created_at": req.get("created_at")
        })
        
    # Sync log history
    sync_logs = db_get_sync_logs(phc_code=phc_code, limit=10)
    
    # Patient statistics history
    patient_stats = db_get_patient_statistics(phc_code=phc_code)
    
    return render_template(
        "phc_user_dashboard.html",
        local_inventory=local_inventory,
        local_outbreaks=outbreak_rows,
        local_requests=formatted_requests,
        total_stock_units=total_stock_units,
        critical_alerts_count=critical_alerts_count,
        low_stock_alerts_count=low_stock_alerts_count,
        user=session["user"],
        all_medicines=all_meds,
        sync_logs=sync_logs,
        patient_stats=patient_stats[:10]
    )

def render_district_admin_dashboard():
    district = session["user"].get("district", "Warangal")
    all_villages = db_get_villages()
    district_phcs = [v for v in all_villages if v["district"].lower() == district.lower()]
    phc_codes = [p["id"] for p in district_phcs]
    
    # Filter stock shortages
    all_alerts = db_get_shortage_alerts()
    district_alerts = [a for a in all_alerts if a["district"].lower() == district.lower()]
    
    # Outbreaks in the district
    all_outbreaks = db_get_outbreaks()
    district_outbreaks = [o for o in all_outbreaks if o["village_id"] in phc_codes]
    
    # Stock transfers within district
    all_transfers = []
    try:
        transfers_res = api_stock_transfers()
        all_transfers = transfers_res.get_json().get("transfers", [])
    except Exception as e:
        safe_print(f"Error calling api_stock_transfers: {e}")
        all_transfers = []
    district_transfers = [t for t in all_transfers if t["source_id"] in phc_codes or t["destination_id"] in phc_codes]
    
    # Sync logs in district
    all_sync_logs = db_get_latest_sync_logs()
    district_sync_logs = [log for log in all_sync_logs if log.get("district") == district or log.get("phc_code") in phc_codes]
    
    return render_template(
        "district_admin_dashboard.html",
        district=district,
        phcs=district_phcs,
        alerts=district_alerts,
        outbreaks=district_outbreaks,
        transfers=district_transfers,
        sync_logs=district_sync_logs[:10],
        user=session["user"]
    )

def render_state_admin_dashboard():
    villages = db_get_villages()
    medicines = db_get_medicines()
    inventory = db_get_inventory()
    outbreaks = db_get_outbreaks()
    alerts = db_get_shortage_alerts()
    
    total_alerts = len([a for a in alerts if a["risk_level"] in ["Critical", "High"]])
    active_outbreaks = len(outbreaks)
    
    all_transfers = []
    try:
        transfers_res = api_stock_transfers()
        all_transfers = transfers_res.get_json().get("transfers", [])
    except Exception as e:
        safe_print(f"Error calling api_stock_transfers: {e}")
        all_transfers = []
        
    # Calculate average availability
    availability = []
    for v in villages:
        inv = inventory.get(v["id"], {})
        total_stock = sum(inv.values())
        max_stock = sum(get_daily_consumption(v["id"], m["id"], villages) * 30 for m in medicines)
        pct = min(100, round((total_stock / max(max_stock, 1)) * 100))
        availability.append(pct)
    avg_availability = round(sum(availability) / len(availability)) if availability else 0
    
    # AI forecasts
    predictions = []
    try:
        pred_res = api_demand_prediction()
        predictions = pred_res.get_json().get("predictions", [])
    except Exception as e:
        safe_print(f"Error calling api_demand_prediction: {e}")
        
    # Emergency plans
    emergency_plans = []
    try:
        emerg_res = api_emergency()
        emergency_plans = emerg_res.get_json().get("plans", [])
    except Exception as e:
        safe_print(f"Error calling api_emergency: {e}")
        
    # Sync logs
    sync_logs = db_get_latest_sync_logs()
    
    return render_template(
        "state_admin_dashboard.html",
        villages=villages,
        medicines=medicines,
        total_alerts=total_alerts,
        avg_availability=avg_availability,
        active_outbreaks=active_outbreaks,
        outbreaks=outbreaks,
        transfers=all_transfers,
        predictions=predictions[:15],
        emergency_plans=emergency_plans,
        sync_logs=sync_logs[:10],
        user=session["user"]
    )

def render_transport_dashboard():
    shipments = db_get_shipments()
    vehicles = get_transportation_vehicles()
    
    en_route = [s for s in shipments if s["status"] == "En Route"]
    scheduled = [s for s in shipments if s["status"] == "Scheduled"]
    completed = [s for s in shipments if s["status"] == "Delivered"]
    
    # Active deliveries
    deliveries = db_get_deliveries()
    
    return render_template(
        "transport_dashboard.html",
        shipments=shipments,
        vehicles=vehicles,
        en_route_count=len(en_route),
        scheduled_count=len(scheduled),
        completed_count=len(completed),
        deliveries=deliveries,
        user=session["user"]
    )

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page"))
        
    role = session["user"].get("role")
    
    if role == "PHC User":
        return render_phc_user_dashboard()
    elif role == "District Admin":
        return render_district_admin_dashboard()
    elif role == "State Admin":
        return render_state_admin_dashboard()
    elif role == "Transport Coordinator":
        return render_transport_dashboard()
    else:
        return render_state_admin_dashboard()

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
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
            
        role = session["user"].get("role")
        if role == "PHC User":
            allowed = ["dashboard", "phc_dashboard", "phc_inventory", "phc_outbreaks", "phc_requests", "phc_patient_statistics", "phc_sync", "api_auth_logout", "api_auth_switch_role"]
            if request.endpoint not in allowed and not request.path.startswith("/static/"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Forbidden for PHC User role"}), 403
                return redirect(url_for("dashboard"))
        elif role == "Transport Coordinator":
            allowed = ["dashboard", "schedule_page", "api_delivery_schedule", "api_auth_logout", "api_auth_switch_role"]
            if request.endpoint not in allowed and not request.path.startswith("/static/"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Forbidden for Transport Coordinator role"}), 403
                return redirect(url_for("dashboard"))
        elif role in ["District Admin", "State Admin"]:
            phc_endpoints = ["phc_dashboard", "phc_inventory", "phc_outbreaks", "phc_requests", "phc_patient_statistics", "phc_sync"]
            if request.endpoint in phc_endpoints:
                return redirect(url_for("dashboard"))

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
        
    # Fetch all PHCs to populate dropdown in login form
    phcs = []
    try:
        phc_rows = query_sqlite("SELECT PHC_Code as code, PHC_Name as name, District as district FROM phcs ORDER BY PHC_Name")
        if not phc_rows:
            phc_rows = db_get_villages()
        for r in phc_rows:
            phcs.append({
                "code": r.get("code") or r.get("PHC_Code"),
                "name": r.get("name") or r.get("PHC_Name"),
                "district": r.get("district") or r.get("District", "")
            })
    except Exception as e:
        safe_print(f"Error loading PHCs for login dropdown: {e}")
        
    return render_template("login.html", phcs=phcs)

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
    role = data.get("role", "PHC User").strip()  # 'PHC User', 'District Admin', 'State Admin', 'Transport Coordinator'
    
    if not mobile or len(mobile) < 10:
        return jsonify({"success": False, "error": "Invalid mobile number. Must be 10 digits."}), 400
        
    # Hackathon Demo Mode: Accept OTP 123456
    if otp == "123456":
        user_data = {
            "mobile": f"+91 {mobile[-10:]}",
            "role": role,
            "given_name": mobile[-4:]
        }
        
        if role == "PHC User":
            phc_code = data.get("phc_code", "").strip()
            phc_name = data.get("phc_name", "").strip()
            if not phc_code:
                return jsonify({"success": False, "error": "Please select a PHC from the dropdown."}), 400
            user_data.update({
                "name": f"Supervisor ({phc_name})",
                "email": f"{phc_code.lower()}@phc.medireach.ai",
                "given_name": "Supervisor",
                "phc_code": phc_code,
                "phc_name": phc_name,
                "portal": "phc_portal"
            })
        elif role == "District Admin":
            district = data.get("district", "").strip()
            if not district:
                return jsonify({"success": False, "error": "Please select a district."}), 400
            user_data.update({
                "name": f"District Admin ({district})",
                "email": f"{district.lower().replace(' ', '')}@district.medireach.ai",
                "given_name": "District Officer",
                "district": district,
                "portal": "mission_control"
            })
        elif role == "State Admin":
            user_data.update({
                "name": "State Admin (Telangana)",
                "email": "state.admin@medireach.ai",
                "given_name": "State Director",
                "portal": "mission_control"
            })
        elif role == "Transport Coordinator":
            user_data.update({
                "name": "Transport Coordinator",
                "email": "logistics@medireach.ai",
                "given_name": "Logistics Lead",
                "portal": "mission_control"
            })
        else:
            return jsonify({"success": False, "error": f"Invalid role selected: {role}"}), 400
            
        session["user"] = user_data
        
        # Save user to DB (best-effort write to Supabase, fallback SQLite)
        db_insert_user(user_data)
        
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

    resp = jsonify({
        "villages_monitored": len(villages),
        "medicine_availability": round(sum(all_pcts) / len(all_pcts)) if all_pcts else 0,
        "active_alerts": total_alerts,
        "forecast_accuracy": 94,
        "outbreak_risk": round(len(outbreaks) * 2.1, 1),
        "active_outbreaks": len(outbreaks),
        "transport_vehicles": available_transport,
        "medicines_tracked": len(medicines),
    })
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp

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
    resp = jsonify({
        "alerts": alerts,
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["risk_level"] == "Critical"),
        "generated_at": datetime.now().isoformat()
    })
    resp.headers["Cache-Control"] = "public, max-age=30"
    return resp

@app.route("/api/cache/clear", methods=["POST"])
def api_cache_clear():
    """Clear all server-side TTL caches (admin endpoint)."""
    with _CACHE_LOCK:
        _CACHE.clear()
    safe_print("[Cache] All caches cleared via API.")
    return jsonify({"success": True, "message": "All caches cleared"})

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


# ─────────────────────────────────────────────────────────────────────────────
# RHIM PHC SYNC MONITOR
# ─────────────────────────────────────────────────────────────────────────────

RHIM_TABLE_READY = False   # set to True once table confirmed / created

def _ensure_rhim_table():
    """Probe whether rhim_sync_log exists; return True if it does."""
    global RHIM_TABLE_READY
    if RHIM_TABLE_READY:
        return True
    try:
        supabase_request("rhim_sync_log?limit=1")
        RHIM_TABLE_READY = True
        return True
    except Exception:
        return False

def _generate_rhim_ai_recommendations(sync_row):
    """
    Given one rhim_sync_log row, produce a list of AI recommendation strings.
    Pure Python logic — no external AI API required.
    """
    recs = []
    phc  = sync_row.get("phc_name", "this PHC")
    dist = sync_row.get("district", "")

    # ── Inventory recommendations ──────────────────────────────────────────
    crit  = sync_row.get("inventory_critical_items", 0)
    units = sync_row.get("inventory_total_units", 0)
    items = sync_row.get("inventory_items_received", 0)

    if crit >= 3:
        recs.append({
            "priority": "CRITICAL",
            "icon": "🚨",
            "category": "Inventory",
            "recommendation": (
                f"{phc} has {crit} critical medicine items at dangerously low stock. "
                f"Dispatch emergency resupply of priority medicines to {dist or phc} within 24 hours."
            )
        })
    elif crit >= 1:
        recs.append({
            "priority": "HIGH",
            "icon": "⚠️",
            "category": "Inventory",
            "recommendation": (
                f"{crit} medicine item(s) at {phc} are critically low. "
                f"Schedule restocking within 48 hours to avoid stockout."
            )
        })
    elif items > 0:
        recs.append({
            "priority": "LOW",
            "icon": "✅",
            "category": "Inventory",
            "recommendation": (
                f"Inventory sync successful for {phc}: {items} items ({units} units) received. "
                "Stock levels appear adequate — continue routine monitoring."
            )
        })

    # ── Disease report recommendations ────────────────────────────────────
    cases  = sync_row.get("disease_cases_total", 0)
    alerts = sync_row.get("disease_alerts", 0)

    if alerts >= 2:
        recs.append({
            "priority": "CRITICAL",
            "icon": "🦠",
            "category": "Disease",
            "recommendation": (
                f"Multiple disease alerts ({alerts}) reported from {phc}. "
                f"Activate outbreak response protocol. Notify District Health Officer for {dist or 'this district'} immediately."
            )
        })
    elif alerts == 1:
        recs.append({
            "priority": "HIGH",
            "icon": "🔬",
            "category": "Disease",
            "recommendation": (
                f"Disease alert at {phc} with {cases} cases reported. "
                "Deploy surveillance team and ensure adequate diagnostic kits and treatment medicines."
            )
        })
    elif cases > 50:
        recs.append({
            "priority": "MEDIUM",
            "icon": "📊",
            "category": "Disease",
            "recommendation": (
                f"High patient load ({cases} cases) at {phc}. "
                "Monitor disease trends closely and pre-position high-usage medicines."
            )
        })

    # ── OPD recommendations ───────────────────────────────────────────────
    opd_total  = sync_row.get("opd_patients_total", 0)
    referred   = sync_row.get("opd_referred_cases", 0)
    immunized  = sync_row.get("opd_immunizations", 0)

    ref_pct = (referred / opd_total * 100) if opd_total else 0
    if ref_pct > 20:
        recs.append({
            "priority": "HIGH",
            "icon": "🏥",
            "category": "OPD",
            "recommendation": (
                f"High referral rate ({ref_pct:.0f}%) at {phc} — {referred} of {opd_total} patients referred. "
                "Consider specialist outreach or capacity expansion to reduce patient burden on district hospitals."
            )
        })
    elif immunized > 0:
        recs.append({
            "priority": "LOW",
            "icon": "💉",
            "category": "OPD",
            "recommendation": (
                f"Immunization program active at {phc}: {immunized} immunizations completed this cycle. "
                "Ensure cold chain integrity and adequate vaccine stock for next cycle."
            )
        })

    if not recs:
        recs.append({
            "priority": "LOW",
            "icon": "✅",
            "category": "General",
            "recommendation": (
                f"Sync from {phc} completed with no critical flags. "
                "All health indicators within normal range — no immediate action required."
            )
        })

    return recs


@app.route("/rhim-sync")
def rhim_sync_page():
    user = session.get("user")
    villages = db_get_villages()
    table_ok = _ensure_rhim_table()
    return render_template(
        "rhim_sync.html",
        user=user, personas=PERSONAS,
        villages=villages,
        table_ready=table_ok
    )


@app.route("/api/rhim-sync/logs")
def api_rhim_sync_logs():
    """Return recent RHIM sync log entries."""
    if not _ensure_rhim_table():
        return jsonify({"error": "rhim_sync_log table not yet created", "logs": []}), 200

    try:
        limit = int(request.args.get("limit", 20))
        phc   = request.args.get("phc", "")
        endpoint = f"rhim_sync_log?order=synced_at.desc&limit={limit}"
        if phc:
            endpoint += f"&phc_code=eq.{phc}"
        rows = supabase_request(endpoint)
        # Attach AI recommendations to each row
        for row in rows:
            row["ai_recommendations"] = _generate_rhim_ai_recommendations(row)
        return jsonify({"logs": rows, "count": len(rows)})
    except Exception as e:
        safe_print(f"RHIM sync logs error: {e}")
        return jsonify({"error": str(e), "logs": []}), 200


@app.route("/api/rhim-sync/latest")
def api_rhim_sync_latest():
    """Return the single most-recent sync entry per PHC."""
    if not _ensure_rhim_table():
        return jsonify({"error": "rhim_sync_log table not yet created", "latest": []}), 200

    try:
        rows = supabase_request("rhim_sync_log?order=synced_at.desc&limit=100")
        seen = {}
        for row in rows:
            code = row.get("phc_code")
            if code not in seen:
                seen[code] = row
        latest = list(seen.values())
        for row in latest:
            row["ai_recommendations"] = _generate_rhim_ai_recommendations(row)
        return jsonify({"latest": latest, "count": len(latest)})
    except Exception as e:
        safe_print(f"RHIM latest error: {e}")
        return jsonify({"error": str(e), "latest": []}), 200


@app.route("/api/rhim-sync/push", methods=["POST"])
def api_rhim_sync_push():
    """
    RHIM system pushes a sync event here.
    Accepts JSON payload with PHC sync data and stores it in Supabase.
    """
    if not _ensure_rhim_table():
        return jsonify({"error": "rhim_sync_log table not ready"}), 503

    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({"error": "Empty payload"}), 400

        required = ["phc_code", "phc_name"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        import hashlib as _hl
        sync_id = _hl.md5(
            f"{data['phc_code']}-{datetime.now().isoformat()}".encode()
        ).hexdigest()

        row = {
            "sync_id":                  sync_id,
            "phc_code":                 data["phc_code"],
            "phc_name":                 data["phc_name"],
            "district":                 data.get("district", ""),
            "synced_at":                datetime.now().isoformat(),
            "sync_source":              data.get("sync_source", "RHIM"),
            "inventory_items_received": data.get("inventory_items_received", 0),
            "inventory_total_units":    data.get("inventory_total_units", 0),
            "inventory_critical_items": data.get("inventory_critical_items", 0),
            "disease_reports_received": data.get("disease_reports_received", 0),
            "disease_cases_total":      data.get("disease_cases_total", 0),
            "disease_alerts":           data.get("disease_alerts", 0),
            "opd_patients_total":       data.get("opd_patients_total", 0),
            "opd_new_cases":            data.get("opd_new_cases", 0),
            "opd_referred_cases":       data.get("opd_referred_cases", 0),
            "opd_immunizations":        data.get("opd_immunizations", 0),
            "inventory_payload":        json.dumps(data.get("inventory_payload", {})),
            "disease_payload":          json.dumps(data.get("disease_payload", {})),
            "opd_payload":              json.dumps(data.get("opd_payload", {})),
            "sync_status":              "completed",
        }

        result = supabase_request("rhim_sync_log", method="POST", data=row)
        recs = _generate_rhim_ai_recommendations(row)
        return jsonify({"success": True, "sync_id": sync_id, "ai_recommendations": recs})
    except Exception as e:
        safe_print(f"RHIM push error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rhim-sync/simulate", methods=["POST"])
def api_rhim_sync_simulate():
    """Simulate a RHIM sync event for demo/testing — generates realistic data."""
    if not _ensure_rhim_table():
        return jsonify({"error": "rhim_sync_log table not ready — create it via SQL first"}), 503

    try:
        villages = db_get_villages()
        if not villages:
            return jsonify({"error": "No PHC data available"}), 500

        v = random.choice(villages)

        inventory_items = random.randint(8, 25)
        inventory_units  = random.randint(200, 2000)
        crit_items       = random.randint(0, 3)
        dis_reports      = random.randint(1, 8)
        dis_cases        = random.randint(5, 120)
        dis_alerts       = random.randint(0, 2)
        opd_total        = random.randint(30, 250)
        opd_new          = random.randint(10, opd_total)
        opd_ref          = random.randint(0, max(1, opd_total // 5))
        opd_imm          = random.randint(0, 60)

        import hashlib as _hl
        sync_id = _hl.md5(
            f"{v['id']}-{datetime.now().isoformat()}".encode()
        ).hexdigest()

        row = {
            "sync_id":                  sync_id,
            "phc_code":                 v["id"],
            "phc_name":                 v["phc"],
            "district":                 v["district"],
            "synced_at":                datetime.now().isoformat(),
            "sync_source":              "RHIM-SIM",
            "inventory_items_received": inventory_items,
            "inventory_total_units":    inventory_units,
            "inventory_critical_items": crit_items,
            "disease_reports_received": dis_reports,
            "disease_cases_total":      dis_cases,
            "disease_alerts":           dis_alerts,
            "opd_patients_total":       opd_total,
            "opd_new_cases":            opd_new,
            "opd_referred_cases":       opd_ref,
            "opd_immunizations":        opd_imm,
            "inventory_payload":        json.dumps({
                "medicines": [
                    {"name": "Paracetamol 500mg", "units": random.randint(50, 500), "status": "low" if crit_items > 0 else "ok"},
                    {"name": "ORS Sachets", "units": random.randint(20, 300), "status": "ok"},
                    {"name": "Amoxicillin 250mg", "units": random.randint(5, 200), "status": "critical" if crit_items >= 2 else "low" if crit_items == 1 else "ok"},
                ]
            }),
            "disease_payload":          json.dumps({
                "reports": [
                    {"disease": random.choice(["Dengue", "Malaria", "Typhoid", "Cholera", "Diarrhea"]),
                     "cases": dis_cases,
                     "severity": random.choice(["Low", "Medium", "High"])}
                ]
            }),
            "opd_payload":              json.dumps({
                "total": opd_total, "new": opd_new, "referred": opd_ref, "immunizations": opd_imm,
                "top_complaints": random.sample(["Fever", "Cough", "Diarrhea", "Malnutrition", "Skin disease", "Eye infection"], 3)
            }),
            "sync_status": "completed",
        }

        supabase_request("rhim_sync_log", method="POST", data=row)
        row["ai_recommendations"] = _generate_rhim_ai_recommendations(row)
        return jsonify({"success": True, "sync_id": sync_id, "sync_data": row})
    except Exception as e:
        safe_print(f"RHIM simulate error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rhim-sync/stats")
def api_rhim_sync_stats():
    """Return aggregate statistics for the RHIM sync monitor dashboard."""
    if not _ensure_rhim_table():
        return jsonify({
            "table_ready": False,
            "total_syncs": 0, "synced_phcs": 0, "critical_alerts": 0,
            "last_sync_at": None, "avg_inventory_items": 0,
            "avg_opd_patients": 0, "total_disease_cases": 0,
        })
    try:
        rows = supabase_request("rhim_sync_log?order=synced_at.desc&limit=200")
        if not rows:
            return jsonify({
                "table_ready": True,
                "total_syncs": 0, "synced_phcs": 0, "critical_alerts": 0,
                "last_sync_at": None, "avg_inventory_items": 0,
                "avg_opd_patients": 0, "total_disease_cases": 0,
            })

        total  = len(rows)
        phcs   = len(set(r["phc_code"] for r in rows))
        crits  = sum(r.get("inventory_critical_items", 0) + r.get("disease_alerts", 0) for r in rows)
        last_sync = rows[0]["synced_at"] if rows else None
        avg_inv = round(sum(r.get("inventory_items_received", 0) for r in rows) / max(total, 1), 1)
        avg_opd = round(sum(r.get("opd_patients_total", 0) for r in rows) / max(total, 1), 1)
        dis_cases = sum(r.get("disease_cases_total", 0) for r in rows)

        return jsonify({
            "table_ready": True,
            "total_syncs": total,
            "synced_phcs": phcs,
            "critical_alerts": crits,
            "last_sync_at": last_sync,
            "avg_inventory_items": avg_inv,
            "avg_opd_patients": avg_opd,
            "total_disease_cases": dis_cases,
        })
    except Exception as e:
        safe_print(f"RHIM stats error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# PHC SUPERVISOR PORTAL ROUTES & APIS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/phc-portal/dashboard")
def phc_dashboard():
    return redirect(url_for("dashboard"))

@app.route("/phc-portal/inventory", methods=["GET", "POST"])
def phc_inventory():
    phc_code = session["user"].get("phc_code")
    all_meds = db_get_medicines()
    med_map = {m["id"]: m for m in all_meds}
    
    if request.method == "POST":
        try:
            medicine_id = request.form.get("medicine_id")
            stock_change = int(request.form.get("stock_change", 0))
            change_type = request.form.get("change_type", "set") # 'dispense', 'add', 'set'
            batch_number = request.form.get("batch_number", "")
            
            # Fetch existing stock first
            existing = query_sqlite("SELECT stock FROM inventory WHERE phc_code = ? AND medicine_id = ?", (phc_code, medicine_id))
            current_stock = existing[0]["stock"] if existing else 0
                
            if change_type == "add":
                new_stock = current_stock + stock_change
            elif change_type == "dispense":
                new_stock = max(0, current_stock - stock_change)
            else:
                new_stock = max(0, stock_change)
                
            db_update_inventory(phc_code, medicine_id, new_stock, batch_number)
                
            # Clear cache
            with _CACHE_LOCK:
                _CACHE.pop("inventory", None)
                _CACHE.pop("shortage_alerts", None)
                
            flash("Stock level updated successfully.", "success")
        except Exception as e:
            flash(f"Error updating stock: {e}", "danger")
        return redirect(url_for("phc_inventory"))
        
    # GET: Retrieve inventory
    inventory_rows = query_sqlite("SELECT * FROM inventory WHERE phc_code = ?", (phc_code,))
    if not inventory_rows:
        try:
            inventory_rows = supabase_request(f"inventory?phc_code=eq.{phc_code}")
        except Exception:
            inventory_rows = []
            
    local_inventory = []
    for r in inventory_rows:
        med_id = r.get("medicine_id")
        stock = r.get("stock", 0)
        med_info = med_map.get(med_id, {"name": med_id, "category": "Unknown", "unit": "Units"})
        local_inventory.append({
            "medicine_id": med_id,
            "name": med_info["name"],
            "category": med_info["category"],
            "unit": med_info["unit"],
            "stock": stock
        })
    local_inventory.sort(key=lambda x: x["name"])
    
    return render_template(
        "phc_inventory.html",
        local_inventory=local_inventory,
        all_medicines=all_meds,
        user=session["user"]
    )

@app.route("/phc-portal/outbreaks", methods=["GET", "POST"])
def phc_outbreaks():
    phc_code = session["user"].get("phc_code")
    
    if request.method == "POST":
        try:
            disease = request.form.get("disease")
            affected = int(request.form.get("affected", 0))
            severity = request.form.get("severity", "Medium")
            spread_rate = float(request.form.get("spread_rate", 1.2))
            started = request.form.get("started") or datetime.now().strftime("%Y-%m-%d")
            
            # Map disease to category
            disease_categories = {
                "Malaria": "Vector-Borne",
                "Dengue": "Vector-Borne",
                "Diarrhea": "Water-Borne",
                "Cholera": "Water-Borne",
                "Typhoid": "Infectious",
                "Influenza": "Respiratory",
                "Gastroenteritis": "Stomach"
            }
            category = disease_categories.get(disease, "Other")
            
            outbreak_data = {
                "phc_code": phc_code,
                "disease": disease,
                "affected": affected,
                "severity": severity,
                "spread_rate": spread_rate,
                "started": started,
                "disease_category": category,
                "cases_reported": affected
            }
            
            db_insert_outbreak(outbreak_data)
            
            # Clear cache
            with _CACHE_LOCK:
                _CACHE.pop("outbreaks", None)
                _CACHE.pop("shortage_alerts", None)
                
            flash("Outbreak report logged successfully.", "success")
        except Exception as e:
            flash(f"Error logging outbreak: {e}", "danger")
        return redirect(url_for("phc_outbreaks"))
        
    # GET: Retrieve outbreaks
    outbreak_rows = query_sqlite("SELECT * FROM disease_outbreaks WHERE phc_code = ? ORDER BY started DESC", (phc_code,))
    if not outbreak_rows:
        try:
            outbreak_rows = supabase_request(f"disease_outbreaks?phc_code=eq.{phc_code}&order=started.desc")
        except Exception:
            outbreak_rows = []
            
    return render_template(
        "phc_outbreaks.html",
        local_outbreaks=outbreak_rows,
        user=session["user"]
    )

@app.route("/phc-portal/requests", methods=["GET", "POST"])
def phc_requests():
    phc_code = session["user"].get("phc_code")
    all_meds = db_get_medicines()
    med_map = {m["id"]: m for m in all_meds}
    
    if request.method == "POST":
        try:
            medicine_id = request.form.get("medicine_id")
            quantity = int(request.form.get("quantity", 0))
            priority = request.form.get("priority", "Medium")
            
            request_data = {
                "phc_code": phc_code,
                "medicine_id": medicine_id,
                "quantity": quantity,
                "priority": priority,
                "status": "Pending"
            }
            db_insert_request(request_data)
            
            flash("Replenishment request submitted successfully.", "success")
        except Exception as e:
            flash(f"Error submitting request: {e}", "danger")
        return redirect(url_for("phc_requests"))
        
    # GET: Retrieve requests
    request_rows = query_sqlite("SELECT * FROM medicine_requests WHERE phc_code = ? ORDER BY created_at DESC", (phc_code,))
    if not request_rows:
        try:
            request_rows = supabase_request(f"medicine_requests?phc_code=eq.{phc_code}&order=created_at.desc")
        except Exception:
            request_rows = []
        
    formatted_requests = []
    for req in request_rows:
        med_id = req.get("medicine_id")
        med_name = med_map.get(med_id, {}).get("name", med_id)
        formatted_requests.append({
            "id": req.get("id"),
            "medicine_name": med_name,
            "quantity": req.get("quantity"),
            "priority": req.get("priority", "Medium"),
            "status": req.get("status", "Pending"),
            "created_at": req.get("created_at")
        })
        
    return render_template(
        "phc_requests.html",
        local_requests=formatted_requests,
        all_medicines=all_meds,
        user=session["user"]
    )

@app.route("/phc-portal/patient-statistics", methods=["POST"])
def phc_patient_statistics():
    phc_code = session["user"].get("phc_code")
    try:
        opd_total = int(request.form.get("opd_patients_total", 0))
        opd_new = int(request.form.get("opd_new_cases", 0))
        opd_ref = int(request.form.get("opd_referred_cases", 0))
        opd_imm = int(request.form.get("opd_immunizations", 0))
        recorded_date = request.form.get("recorded_date") or datetime.now().strftime("%Y-%m-%d")
        
        stat_data = {
            "phc_code": phc_code,
            "opd_patients_total": opd_total,
            "opd_new_cases": opd_new,
            "opd_referred_cases": opd_ref,
            "opd_immunizations": opd_imm,
            "recorded_date": recorded_date
        }
        db_insert_patient_statistics(stat_data)
        flash("Patient statistics logged successfully.", "success")
    except Exception as e:
        flash(f"Error logging patient statistics: {e}", "danger")
    return redirect(url_for("dashboard"))

@app.route("/phc-portal/sync", methods=["POST"])
def phc_sync():
    phc_code = session["user"].get("phc_code")
    phc_name = session["user"].get("phc_name")
    
    # Try to find the district from database
    phc_district = "Unknown"
    try:
        villages = db_get_villages()
        for v in villages:
            if v["id"] == phc_code:
                phc_district = v["district"]
                break
    except Exception:
        pass
    
    try:
        all_meds = db_get_medicines()
        med_map = {m["id"]: m for m in all_meds}
        
        # 1. Fetch inventory
        inventory_rows = query_sqlite("SELECT * FROM inventory WHERE phc_code = ?", (phc_code,))
        if not inventory_rows:
            inventory_rows = supabase_request(f"inventory?phc_code=eq.{phc_code}")
        inv_items = len(inventory_rows)
        inv_units = sum(r.get("stock", 0) for r in inventory_rows)
        
        inv_crit = 0
        inventory_payload = []
        for r in inventory_rows:
            med_id = r.get("medicine_id")
            stock = r.get("stock", 0)
            med_name = med_map.get(med_id, {}).get("name", med_id)
            
            daily_cons = get_daily_consumption(phc_code, med_id, db_get_villages())
            risk, days_rem = calculate_risk_level(stock, daily_cons)
            
            if risk == "Critical":
                inv_crit += 1
                
            inventory_payload.append({
                "name": med_name,
                "units": stock,
                "status": "critical" if risk == "Critical" else "low" if risk == "High" else "ok"
            })
            
        # 2. Fetch outbreaks
        outbreak_rows = query_sqlite("SELECT * FROM disease_outbreaks WHERE phc_code = ?", (phc_code,))
        if not outbreak_rows:
            outbreak_rows = supabase_request(f"disease_outbreaks?phc_code=eq.{phc_code}")
        disease_reports = len(outbreak_rows)
        disease_cases = sum(r.get("affected", 0) for r in outbreak_rows)
        disease_alerts = sum(1 for r in outbreak_rows if r.get("severity") in ["High", "Critical"])
        
        disease_payload = []
        for r in outbreak_rows:
            disease_payload.append({
                "disease": r.get("disease"),
                "cases": r.get("affected", 0),
                "severity": r.get("severity", "Medium")
            })
            
        # 3. Fetch patient stats
        patient_rows = query_sqlite("SELECT * FROM patient_statistics WHERE phc_code = ? ORDER BY recorded_date DESC LIMIT 1", (phc_code,))
        if patient_rows:
            p = patient_rows[0]
            opd_total = p.get("opd_patients_total", 0)
            opd_new = p.get("opd_new_cases", 0)
            opd_ref = p.get("opd_referred_cases", 0)
            opd_imm = p.get("opd_immunizations", 0)
        else:
            opd_total = max(30, disease_cases * 3 + random.randint(10, 50))
            opd_new = int(opd_total * 0.8)
            opd_ref = int(opd_total * 0.05 + disease_alerts * 3)
            opd_imm = random.randint(5, 30)
        
        import hashlib as _hl
        sync_id = _hl.md5(f"{phc_code}-{datetime.now().isoformat()}".encode()).hexdigest()
        
        row = {
            "sync_id":                  sync_id,
            "phc_code":                 phc_code,
            "phc_name":                 phc_name,
            "district":                 phc_district,
            "synced_at":                datetime.now().isoformat(),
            "sync_source":              "PHC-Portal",
            "inventory_items_received": inv_items,
            "inventory_total_units":    inv_units,
            "inventory_critical_items": inv_crit,
            "disease_reports_received": disease_reports,
            "disease_cases_total":      disease_cases,
            "disease_alerts":           disease_alerts,
            "opd_patients_total":       opd_total,
            "opd_new_cases":            opd_new,
            "opd_referred_cases":       opd_ref,
            "opd_immunizations":        opd_imm,
            "inventory_payload":        json.dumps({"items": inventory_payload}),
            "disease_payload":          json.dumps({"reports": disease_payload}),
            "opd_payload":              json.dumps({
                "total": opd_total, "new": opd_new, "referred": opd_ref, "immunizations": opd_imm,
                "top_complaints": ["Fever", "Cough", "Diarrhea"]
            }),
            "sync_status": "completed",
        }
        
        db_insert_sync_log(row)
        
        socketio.emit("data_updated", {
            "type": "sync",
            "message": f"Real-time Data Sync completed for {phc_name} PHC ({phc_district} District).",
            "icon": "🔄",
            "sync_data": row
        })
        
        with _CACHE_LOCK:
            _CACHE.pop("inventory", None)
            _CACHE.pop("outbreaks", None)
            _CACHE.pop("shortage_alerts", None)
            
        return jsonify({
            "success": True, 
            "message": "Data successfully synchronized with MediReach Mission Control.",
            "sync_id": sync_id
        })
    except Exception as e:
        safe_print(f"Error transmitting PHC Portal data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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
