# Seeding Script for MediReach AI v2 (20 Medicines & Warehouse Supervisor Schema)
import urllib.request
import json
import random
import time
from datetime import datetime, timedelta

url_base = "https://fhzicqsekyccqknjwmuc.supabase.co/rest/v1"
headers = {
    "apikey": "sb_publishable_OLXix_wLaKB7g1CoXF8FNg_Ygj8GjiX",
    "Authorization": "Bearer sb_publishable_OLXix_wLaKB7g1CoXF8FNg_Ygj8GjiX",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def post_data(endpoint, data):
    url = f"{url_base}/{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error seeding {endpoint}: {e}")
        return None

def delete_data(endpoint):
    url = f"{url_base}/{endpoint}?id=gt.0"
    req = urllib.request.Request(url, headers=headers, method='DELETE')
    try:
        urllib.request.urlopen(req)
        print(f"Successfully truncated table public.{endpoint}")
    except Exception as e:
        print(f"Error truncating public.{endpoint}: {e}")

def fetch_phcs():
    url = f"{url_base}/phcs?select=PHC_Code,District"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching PHCs: {e}")
        return []

def main():
    print("Fetching PHC codes from Supabase...")
    phcs = fetch_phcs()
    if not phcs:
        print("No PHCs found in Supabase. Cannot proceed with seeding.")
        return
    print(f"Found {len(phcs)} PHC records.")

    # 20 Essential Medicines List
    medicines = [
        {"name": "Paracetamol 500mg", "category": "Antipyretic", "unit": "Tablets", "critical": True},
        {"name": "Chloroquine 250mg", "category": "Antimalarial", "unit": "Tablets", "critical": True},
        {"name": "ORS Sachets", "category": "Rehydration", "unit": "Sachets", "critical": True},
        {"name": "Amoxicillin 500mg", "category": "Antibiotic", "unit": "Capsules", "critical": True},
        {"name": "Metformin 500mg", "category": "Antidiabetic", "unit": "Tablets", "critical": False},
        {"name": "Amlodipine 5mg", "category": "Antihypertensive", "unit": "Tablets", "critical": False},
        {"name": "Vitamin D3 1000IU", "category": "Supplement", "unit": "Capsules", "critical": False},
        {"name": "Albendazole 400mg", "category": "Anthelmintic", "unit": "Tablets", "critical": False},
        {"name": "Dexamethasone 4mg", "category": "Corticosteroid", "unit": "Tablets", "critical": True},
        {"name": "Artemether+Lumef.", "category": "Antimalarial", "unit": "Tablets", "critical": True},
        {"name": "Azithromycin 500mg", "category": "Antibiotic", "unit": "Tablets", "critical": True},
        {"name": "Atorvastatin 10mg", "category": "Lipid-lowering", "unit": "Tablets", "critical": False},
        {"name": "Ibuprofen 400mg", "category": "Analgesic", "unit": "Tablets", "critical": False},
        {"name": "Cetirizine 10mg", "category": "Antihistamine", "unit": "Tablets", "critical": False},
        {"name": "Ranitidine 150mg", "category": "Antacid", "unit": "Tablets", "critical": False},
        {"name": "Salbutamol Inhaler", "category": "Bronchodilator", "unit": "Inhalers", "critical": True},
        {"name": "Metronidazole 400mg", "category": "Antiamoebic", "unit": "Tablets", "critical": False},
        {"name": "Iron + Folic Acid", "category": "Supplement", "unit": "Tablets", "critical": False},
        {"name": "Ciprofloxacin 500mg", "category": "Antibiotic", "unit": "Tablets", "critical": False},
        {"name": "Levothyroxine 50mcg", "category": "Thyroid hormone", "unit": "Tablets", "critical": False}
    ]

    # Truncate existing seed tables to guarantee clean state
    delete_data("logistics_shipments")
    delete_data("warehouses")
    delete_data("inventory")
    delete_data("disease_outbreaks")
    delete_data("patient_statistics")
    delete_data("medicine_predictions")
    delete_data("medicine_shortages")
    delete_data("medicine_transfers")
    delete_data("emergency_plans")

    # 1. Seed Warehouses
    warehouses_data = [
        {"id": "WH-NALG-001", "name": "Nalgonda Depot", "location": "Nalgonda, TS"},
        {"id": "WH-MAHA-002", "name": "Mahabubnagar Depot", "location": "Mahabubnagar, TS"},
        {"id": "WH-WARA-003", "name": "Warangal Depot", "location": "Warangal, TS"},
    ]
    print("Seeding warehouses...")
    post_data("warehouses", warehouses_data)

    # 2. Seed Inventory for all 120 PHCs (20 medicines each)
    print("Generating inventory seeds...")
    inventory_rows = []
    patient_rows = []
    
    for phc in phcs:
        code = phc["PHC_Code"]
        dist = phc["District"]
        
        # Patient demographics
        total_pats = random.randint(150, 600)
        male = int(total_pats * random.uniform(0.40, 0.45))
        female = int(total_pats * random.uniform(0.40, 0.45))
        children = int(total_pats * random.uniform(0.10, 0.15))
        seniors = total_pats - (male + female + children)
        
        patient_rows.append({
            "phc_id": code,
            "total_patients": total_pats,
            "male_patients": male,
            "female_patients": female,
            "children": children,
            "senior_citizens": seniors,
            "recorded_date": datetime.now().strftime("%Y-%m-%d")
        })

        for med in medicines:
            stock = random.randint(100, 1500) if med["critical"] else random.randint(50, 850)
            # Add some critical shortages (12% probability)
            if random.random() < 0.12:
                stock = random.randint(0, 30)
                
            expiry = datetime.now() + timedelta(days=random.randint(180, 720))
            inventory_rows.append({
                "phc_id": code,
                "medicine_name": med["name"],
                "batch_number": f"B-{random.randint(100, 999)}",
                "current_stock": stock,
                "unit": med["unit"],
                "expiry_date": expiry.strftime("%Y-%m-%d")
            })

    print(f"Seeding {len(inventory_rows)} inventory rows in batches...")
    batch_size = 100
    for i in range(0, len(inventory_rows), batch_size):
        post_data("inventory", inventory_rows[i:i+batch_size])
        time.sleep(0.05)

    print("Seeding patient statistics...")
    for i in range(0, len(patient_rows), batch_size):
        post_data("patient_statistics", patient_rows[i:i+batch_size])

    # 3. Seed active disease outbreaks
    print("Generating disease outbreaks...")
    outbreak_categories = ["Vector-Borne", "Water-Borne", "Infectious", "Respiratory"]
    outbreak_rows = []
    
    outbreak_phcs = random.sample(phcs, min(10, len(phcs)))
    for idx, phc in enumerate(outbreak_phcs):
        outbreak_rows.append({
            "phc_id": phc["PHC_Code"],
            "disease_category": outbreak_categories[idx % len(outbreak_categories)],
            "cases_reported": random.randint(15, 80),
            "recorded_date": datetime.now().strftime("%Y-%m-%d")
        })
    post_data("disease_outbreaks", outbreak_rows)

    # 4. Seed Logistics Shipments
    print("Generating logistics dispatches...")
    shipments = []
    vehicles = [
        ("Drone Delivery", "VHL-DRN-10"),
        ("Refrigerated Van", "VHL-VAN-08"),
        ("Medical Truck", "VHL-TRK-03"),
        ("Drone Delivery", "VHL-DRN-15"),
        ("Medical Truck", "VHL-TRK-07")
    ]
    
    dispatch_phcs = random.sample(phcs, min(8, len(phcs)))
    for idx, phc in enumerate(dispatch_phcs):
        v_type, v_id = vehicles[idx % len(vehicles)]
        med = random.choice(medicines)
        wh = random.choice(warehouses_data)
        
        eta = datetime.now() + timedelta(hours=random.randint(2, 12))
        
        shipments.append({
            "id": f"SCH-0{idx+1}",
            "vehicle_type": v_type,
            "vehicle_id": v_id,
            "route": f"Warehouse -> {phc['PHC_Code']}",
            "source_warehouse_id": wh["id"],
            "destination_phc_code": phc["PHC_Code"],
            "medicine_name": med["name"],
            "quantity": random.randint(200, 800),
            "delivery_time": eta.isoformat(),
            "priority": random.choice(["Critical", "High", "Medium"]),
            "road_condition": random.choice(["Good", "Fair", "Poor"]),
            "estimated_hours": random.randint(3, 10),
            "status": random.choice(["Scheduled", "En Route", "Delivered"])
        })
    post_data("logistics_shipments", shipments)

    print("Supabase database seeding completed successfully!")

if __name__ == "__main__":
    main()
