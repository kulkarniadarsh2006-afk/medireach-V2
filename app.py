"""
MediReach AI v2 — Rebuilt Production-Grade Flask Backend
Supabase-First Architecture with Stateless DB Operations & SQLite Fallback
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import random
import os
import urllib.request
import json
import ssl
import sqlite3
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = "medireach_ai_2026_secure"

# Load Supabase Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip('/')
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Missing required environment variables: SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")

# Clean URL for HTTP client
if SUPABASE_URL.endswith('/rest/v1'):
    SUPABASE_URL = SUPABASE_URL[:-8].rstrip('/')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.context_processor
def inject_supabase_config():
    return {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY
    }

# Shared SSL context for SSL bypass (useful for self-signed certificates in local setups)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medireach_local.db")

def safe_print(text):
    try:
        print(text.encode('ascii', 'ignore').decode('ascii'))
    except Exception:
        pass

# ─────────────────────────────────────────────
# DATABASE ACCESS HELPERS (SUPABASE REST & SQLITE FALLBACK)
# ─────────────────────────────────────────────

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
        safe_print(f"[SQLite Error] {e} | Query: {query}")
        return []
    finally:
        conn.close()

def supabase_request(endpoint, method="GET", data=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    req_data = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body) if res_body else []
    except Exception as e:
        safe_print(f"[Supabase HTTP Request Error] {method} on {endpoint}: {e}")
        raise e

# Verify connection on startup
SUPABASE_CONNECTED = False
try:
    supabase_request("phcs?select=PHC_Code&limit=1")
    safe_print("Successfully connected to Supabase PostgreSQL Database!")
    SUPABASE_CONNECTED = True
except Exception as e:
    safe_print(f"Warning: Supabase connection failed: {e}. Operating in Local-First SQLite mode.")

# ─────────────────────────────────────────────
# SQLITE SCHEMA INITIALIZATION
# ─────────────────────────────────────────────

def init_local_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. phcs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS phcs (
        PHC_Code TEXT PRIMARY KEY,
        PHC_Name TEXT NOT NULL,
        District TEXT NOT NULL,
        Population_Covered INTEGER DEFAULT 15000,
        Status TEXT DEFAULT 'Active'
    )
    """)
    
    # 2. users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        phc_id TEXT,
        district TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 3. inventory
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        medicine_name TEXT NOT NULL,
        batch_number TEXT,
        current_stock INTEGER NOT NULL DEFAULT 0,
        unit TEXT DEFAULT 'Units',
        expiry_date TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 4. patient_statistics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patient_statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        total_patients INTEGER NOT NULL DEFAULT 0,
        male_patients INTEGER DEFAULT 0,
        female_patients INTEGER DEFAULT 0,
        children INTEGER DEFAULT 0,
        senior_citizens INTEGER DEFAULT 0,
        recorded_date TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 5. disease_outbreaks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS disease_outbreaks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        disease_category TEXT NOT NULL,
        cases_reported INTEGER NOT NULL DEFAULT 0,
        recorded_date TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 6. medicine_predictions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicine_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        medicine_name TEXT NOT NULL,
        predicted_demand INTEGER NOT NULL DEFAULT 0,
        confidence_pct REAL DEFAULT 90.0,
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 7. medicine_shortages
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicine_shortages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        medicine_name TEXT NOT NULL,
        current_stock INTEGER NOT NULL DEFAULT 0,
        daily_consumption INTEGER NOT NULL DEFAULT 0,
        days_remaining REAL NOT NULL DEFAULT 999.0,
        risk_level TEXT NOT NULL,
        estimated_stockout TEXT,
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 8. emergency_plans
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phc_id TEXT NOT NULL,
        disease TEXT NOT NULL,
        severity TEXT NOT NULL,
        critical_medicines TEXT,
        recommended_vehicle TEXT,
        response_hours INTEGER DEFAULT 12,
        action TEXT DEFAULT 'STANDBY',
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    # 9. medicine_transfers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicine_transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_phc_id TEXT NOT NULL,
        destination_phc_id TEXT NOT NULL,
        medicine_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        priority TEXT DEFAULT 'Medium',
        road_condition TEXT DEFAULT 'Good',
        transport_time INTEGER DEFAULT 4,
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_phc_id) REFERENCES phcs(PHC_Code),
        FOREIGN KEY (destination_phc_id) REFERENCES phcs(PHC_Code)
    )
    """)
    
    conn.commit()
    conn.close()
    safe_print("Local SQLite fallback database tables initialized successfully.")

def seed_local_db_phcs():
    # Query online Supabase database first
    try:
        phcs = supabase_request("phcs?select=*")
        if phcs:
            for p in phcs:
                query_sqlite(
                    "INSERT OR IGNORE INTO phcs (PHC_Code, PHC_Name, District, Population_Covered, Status) VALUES (?, ?, ?, ?, ?)",
                    (p.get("PHC_Code"), p.get("PHC_Name"), p.get("District"), p.get("Population_Covered", 15000), p.get("Status", "Active")),
                    commit=True
                )
            safe_print(f"Seeded {len(phcs)} PHC profiles from Supabase into SQLite!")
            return
    except Exception as e:
        safe_print(f"Failed loading PHCs from Supabase to seed local DB: {e}")
        
    # Default local seeds if offline
    cnt = query_sqlite("SELECT COUNT(*) as count FROM phcs")
    if not cnt or cnt[0]["count"] == 0:
        districts = ["Sangareddy", "Warangal", "Nalgonda", "Mahabubnagar", "Karimnagar", "Khammam", "Nizamabad", "Medak", "Adilabad", "Rangareddy"]
        for idx in range(1, 121):
            code = f"TG-PHC-{idx:04d}"
            name = f"PHC Facility {idx}"
            dist = districts[(idx - 1) % len(districts)]
            query_sqlite(
                "INSERT OR IGNORE INTO phcs (PHC_Code, PHC_Name, District, Population_Covered, Status) VALUES (?, ?, ?, ?, ?)",
                (code, name, dist, 12000 + (idx * 60), "Active"),
                commit=True
            )
        safe_print("Seeded 120 default fallback PHC profiles in SQLite.")

# Initialize databases
init_local_db()
seed_local_db_phcs()

# ─────────────────────────────────────────────
# CONTROLLERS & VIEW ROUTING
# ─────────────────────────────────────────────

@app.context_processor
def inject_user():
    return dict(user=session.get("user"))

@app.before_request
def enforce_login():
    allowed_endpoints = ["index", "login_page", "api_auth_register_profile", "api_auth_login_session", "static", "robots_txt", "sitemap_xml"]
    if request.endpoint and request.endpoint not in allowed_endpoints:
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))

@app.route("/")
def index():
    return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/auth/login-session", methods=["POST"])
def api_auth_login_session():
    try:
        data = request.get_json() or {}
        profile = data.get("profile")
        if profile:
            session["user"] = profile
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "No profile data provided"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.pop("user", None)
    return jsonify({"success": True})

# ─────────────────────────────────────────────
# STATELESS AI ANALYTICS ENGINE ROUTE
# ─────────────────────────────────────────────

@app.route("/api/ai/process", methods=["POST"])
def api_ai_process():
    """
    Stateless AI processing endpoint.
    Queries raw data tables from Supabase (or SQLite fallback), computes demand prediction,
    shortage alerts, emergency response, and transfers, then writes the results back to DB.
    """
    try:
        # 1. Fetch raw logs from database
        phcs = []
        inventory_items = []
        outbreaks = []
        patient_stats = []
        
        try:
            phcs = supabase_request("phcs?select=*")
            inventory_items = supabase_request("inventory?select=*")
            outbreaks = supabase_request("disease_outbreaks?select=*")
            patient_stats = supabase_request("patient_statistics?select=*")
        except Exception:
            # SQLite fallback
            safe_print("[AI Engine] Supabase unreachable. Calculating using SQLite fallback.")
            phcs = query_sqlite("SELECT * FROM phcs")
            inventory_items = query_sqlite("SELECT * FROM inventory")
            outbreaks = query_sqlite("SELECT * FROM disease_outbreaks")
            patient_stats = query_sqlite("SELECT * FROM patient_statistics")
            
        if not phcs:
            return jsonify({"success": False, "error": "No PHC data found to process"}), 400

        # Mappings
        phc_map = {p.get("PHC_Code"): p for p in phcs}
        
        # Standard medicines list to generate predictions for
        medicines = [
            "Paracetamol 500mg", "Chloroquine 250mg", "ORS Sachets", "Amoxicillin 500mg",
            "Metformin 500mg", "Amlodipine 5mg", "Vitamin D3 1000IU", "Albendazole 400mg",
            "Dexamethasone 4mg", "Artemether+Lumef."
        ]
        
        # Base daily consumption per patient rate (per capita factor)
        base_factors = {
            "Paracetamol 500mg": 0.015,
            "Chloroquine 250mg": 0.004,
            "ORS Sachets": 0.008,
            "Amoxicillin 500mg": 0.007,
            "Metformin 500mg": 0.005,
            "Amlodipine 5mg": 0.006,
            "Vitamin D3 1000IU": 0.003,
            "Albendazole 400mg": 0.002,
            "Dexamethasone 4mg": 0.002,
            "Artemether+Lumef.": 0.003
        }

        # Outbreak calculations
        # phc_code -> disease_category -> count
        outbreak_map = {}
        for o in outbreaks:
            code = o.get("phc_id") or o.get("phc_code")
            cat = o.get("disease_category")
            cases = o.get("cases_reported", 0) or o.get("affected", 0)
            if code not in outbreak_map:
                outbreak_map[code] = {}
            outbreak_map[code][cat] = outbreak_map[code].get(cat, 0) + cases

        # ── A. CALCULATE MEDICINE DEMAND PREDICTIONS ──
        predictions_payload = []
        for p in phcs:
            code = p.get("PHC_Code")
            pop = p.get("Population_Covered", 15000)
            local_outbreaks = outbreak_map.get(code, {})
            
            for med in medicines:
                base_cons = pop * base_factors.get(med, 0.003)
                
                # Apply outbreak multipliers
                multiplier = 1.0
                if "Vector-Borne" in local_outbreaks and med in ["Chloroquine 250mg", "Artemether+Lumef."]:
                    multiplier += min(2.5, local_outbreaks["Vector-Borne"] * 0.1)
                if "Water-Borne" in local_outbreaks and med in ["ORS Sachets", "Amoxicillin 500mg"]:
                    multiplier += min(3.0, local_outbreaks["Water-Borne"] * 0.15)
                if "Infectious" in local_outbreaks and med in ["Amoxicillin 500mg"]:
                    multiplier += min(2.0, local_outbreaks["Infectious"] * 0.1)
                if "Respiratory" in local_outbreaks and med in ["Paracetamol 500mg", "Dexamethasone 4mg"]:
                    multiplier += min(1.8, local_outbreaks["Respiratory"] * 0.08)
                
                predicted_14d = int(base_cons * multiplier * 14)
                predictions_payload.append({
                    "phc_id": code,
                    "medicine_name": med,
                    "predicted_demand": max(10, predicted_14d),
                    "confidence_pct": round(85.0 + random.uniform(0.0, 12.0), 1),
                    "generated_at": datetime.now().isoformat()
                })

        # ── B. CALCULATE SHORTAGE DETECTIONS ──
        shortages_payload = []
        # Group inventory by phc_id -> medicine_name -> stock
        inv_map = {}
        for item in inventory_items:
            code = item.get("phc_id") or item.get("phc_code")
            med = item.get("medicine_name") or item.get("medicine_id")
            stock = item.get("current_stock", 0) or item.get("stock", 0)
            if code not in inv_map:
                inv_map[code] = {}
            inv_map[code][med] = stock

        pred_daily_map = {}
        for pred in predictions_payload:
            code = pred["phc_id"]
            med = pred["medicine_name"]
            daily = pred["predicted_demand"] / 14.0
            if code not in pred_daily_map:
                pred_daily_map[code] = {}
            pred_daily_map[code][med] = daily

        for code, meds in inv_map.items():
            for med, stock in meds.items():
                daily_cons = pred_daily_map.get(code, {}).get(med, 10.0)
                if daily_cons <= 0:
                    daily_cons = 1.0
                days_rem = stock / daily_cons
                
                risk_level = "Low"
                if days_rem <= 2:
                    risk_level = "Critical"
                elif days_rem <= 5:
                    risk_level = "High"
                elif days_rem <= 10:
                    risk_level = "Medium"
                
                stockout_date = (datetime.now() + timedelta(days=days_rem)).strftime("%Y-%m-%d")
                shortages_payload.append({
                    "phc_id": code,
                    "medicine_name": med,
                    "current_stock": stock,
                    "daily_consumption": int(daily_cons),
                    "days_remaining": round(days_rem, 1),
                    "risk_level": risk_level,
                    "estimated_stockout": stockout_date,
                    "generated_at": datetime.now().isoformat()
                })

        # ── C. EMERGENCY RESPONSE PLANS ──
        emergency_payload = []
        for o in outbreaks:
            code = o.get("phc_id") or o.get("phc_code")
            cat = o.get("disease_category")
            cases = o.get("cases_reported", 0) or o.get("affected", 0)
            
            if cases >= 10:
                severity = "Medium"
                action = "STANDBY"
                hours = 12
                if cases >= 50:
                    severity = "Critical"
                    action = "IMMEDIATE DISPATCH"
                    hours = 4
                elif cases >= 20:
                    severity = "High"
                    action = "PRIORITY DISPATCH"
                    hours = 8
                
                # Critical allocation list
                allocs = []
                if cat == "Vector-Borne":
                    allocs = [{"medicine": "Artemether+Lumef.", "quantity": cases * 10}, {"medicine": "Chloroquine 250mg", "quantity": cases * 5}]
                elif cat == "Water-Borne":
                    allocs = [{"medicine": "ORS Sachets", "quantity": cases * 15}, {"medicine": "Amoxicillin 500mg", "quantity": cases * 8}]
                else:
                    allocs = [{"medicine": "Paracetamol 500mg", "quantity": cases * 20}]
                
                v_type = "Medical Truck"
                if cases < 25:
                    v_type = "Drone Delivery"
                elif severity == "Critical":
                    v_type = "Refrigerated Van"
                    
                emergency_payload.append({
                    "phc_id": code,
                    "disease": o.get("disease", cat),
                    "severity": severity,
                    "critical_medicines": json.dumps(allocs),
                    "recommended_vehicle": v_type,
                    "response_hours": hours,
                    "action": action,
                    "generated_at": datetime.now().isoformat()
                })

        # ── D. MEDICINE REDISTRIBUTION RECOMMENDATIONS (TRANSFERS) ──
        transfers_payload = []
        # Find potential recipients (Critical/High shortages)
        recipients = [s for s in shortages_payload if s["risk_level"] in ["Critical", "High"]]
        
        # Calculate surplus donors
        donors = []
        for code, meds in inv_map.items():
            for med, stock in meds.items():
                daily_cons = pred_daily_map.get(code, {}).get(med, 10.0)
                days_rem = stock / max(daily_cons, 1.0)
                if days_rem > 20:
                    surplus = int(stock - (daily_cons * 14))
                    if surplus > 50:
                        donors.append({
                            "phc_id": code,
                            "medicine_name": med,
                            "surplus": surplus,
                            "days_remaining": days_rem
                        })

        for rec in recipients:
            rec_code = rec["phc_id"]
            med = rec["medicine_name"]
            
            # Find donor with surplus of this medicine
            best_donor = None
            for d in donors:
                if d["medicine_name"] == med and d["phc_id"] != rec_code:
                    if not best_donor or d["surplus"] > best_donor["surplus"]:
                        best_donor = d
                        
            if best_donor:
                qty_needed = int(pred_daily_map.get(rec_code, {}).get(med, 10.0) * 10 - rec["current_stock"])
                qty_transfer = min(qty_needed, best_donor["surplus"])
                qty_transfer = max(10, qty_transfer)
                
                transfers_payload.append({
                    "source_phc_id": best_donor["phc_id"],
                    "destination_phc_id": rec_code,
                    "medicine_name": med,
                    "quantity": qty_transfer,
                    "priority": rec["risk_level"],
                    "road_condition": random.choice(["Good", "Fair", "Poor"]),
                    "transport_time": random.randint(2, 8),
                    "generated_at": datetime.now().isoformat()
                })
                # Adjust donor surplus
                best_donor["surplus"] -= qty_transfer

        # ── E. WRITE BACK TO DATABASE (SUPABASE OR SQLITE FALLBACK) ──
        try:
            # Delete old calculations on Supabase
            supabase_request("medicine_predictions", method="DELETE")
            supabase_request("medicine_shortages", method="DELETE")
            supabase_request("emergency_plans", method="DELETE")
            supabase_request("medicine_transfers", method="DELETE")
            
            # Bulk Insert predictions
            if predictions_payload:
                # Supabase REST API bulk insert
                supabase_request("medicine_predictions", method="POST", data=predictions_payload)
            if shortages_payload:
                supabase_request("medicine_shortages", method="POST", data=shortages_payload)
            if emergency_payload:
                # Convert string representation of critical_medicines JSON back to dicts/lists
                for ep in emergency_payload:
                    ep["critical_medicines"] = json.loads(ep["critical_medicines"])
                supabase_request("emergency_plans", method="POST", data=emergency_payload)
            if transfers_payload:
                supabase_request("medicine_transfers", method="POST", data=transfers_payload)
                
            safe_print("[AI Engine] Supabase calculation writes completed successfully.")
        except Exception as e:
            safe_print(f"[AI Engine] Supabase write failed: {e}. Writing to SQLite.")
            
            # SQLite Writes
            query_sqlite("DELETE FROM medicine_predictions", commit=True)
            query_sqlite("DELETE FROM medicine_shortages", commit=True)
            query_sqlite("DELETE FROM emergency_plans", commit=True)
            query_sqlite("DELETE FROM medicine_transfers", commit=True)
            
            for p in predictions_payload:
                query_sqlite(
                    "INSERT INTO medicine_predictions (phc_id, medicine_name, predicted_demand, confidence_pct, generated_at) VALUES (?, ?, ?, ?, ?)",
                    (p["phc_id"], p["medicine_name"], p["predicted_demand"], p["confidence_pct"], p["generated_at"]),
                    commit=True
                )
            for s in shortages_payload:
                query_sqlite(
                    "INSERT INTO medicine_shortages (phc_id, medicine_name, current_stock, daily_consumption, days_remaining, risk_level, estimated_stockout) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (s["phc_id"], s["medicine_name"], s["current_stock"], s["daily_consumption"], s["days_remaining"], s["risk_level"], s["estimated_stockout"]),
                    commit=True
                )
            for ep in emergency_payload:
                # For SQLite, store critical_medicines as TEXT
                query_sqlite(
                    "INSERT INTO emergency_plans (phc_id, disease, severity, critical_medicines, recommended_vehicle, response_hours, action) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (ep["phc_id"], ep["disease"], ep["severity"], str(ep["critical_medicines"]), ep["recommended_vehicle"], ep["response_hours"], ep["action"]),
                    commit=True
                )
            for t in transfers_payload:
                query_sqlite(
                    "INSERT INTO medicine_transfers (source_phc_id, destination_phc_id, medicine_name, quantity, priority, road_condition, transport_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (t["source_phc_id"], t["destination_phc_id"], t["medicine_name"], t["quantity"], t["priority"], t["road_condition"], t["transport_time"]),
                    commit=True
                )
            safe_print("[AI Engine] SQLite fallback writes completed successfully.")
            
        return jsonify({"success": True, "message": "Stateless AI processing completed."})
        
    except Exception as e:
        safe_print(f"[AI Engine Error] Processing failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/auth/register-profile", methods=["POST"])
def api_auth_register_profile():
    """
    Called by frontend after user signs up to create their profile mapping role/phc.
    """
    try:
        data = request.get_json() or {}
        uid = data.get("uid")
        email = data.get("email")
        role = data.get("role", "PHC User")
        phc_id = data.get("phc_id")
        district = data.get("district")
        
        if not uid or not email:
            return jsonify({"success": False, "error": "Missing uid or email"}), 400
            
        # Insert user to Supabase
        user_row = {
            "id": uid,
            "email": email,
            "role": role,
            "phc_id": phc_id if phc_id else None,
            "district": district if district else None
        }
        
        try:
            supabase_request("users", method="POST", data=user_row)
        except Exception as e:
            safe_print(f"[Auth Register] Supabase register failed: {e}. Writing to SQLite.")
            query_sqlite(
                "INSERT OR REPLACE INTO users (id, email, role, phc_id, district) VALUES (?, ?, ?, ?, ?)",
                (uid, email, role, phc_id, district),
                commit=True
            )
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────────────────────
# SERVER INITIALIZATION
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("DEBUG", "True").lower() == "true"
    print("\n" + "="*60)
    print("  MediReach AI v2 — Flask Backend")
    print(f"  URL: http://localhost:{port}")
    print("="*60 + "\n")
    socketio.run(app, debug=debug_mode, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
