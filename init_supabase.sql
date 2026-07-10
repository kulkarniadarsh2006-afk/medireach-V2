-- MediReach AI v2 — Supabase Database Schema Initialization
-- Execute this script in your Supabase SQL Editor to set up all required tables, indexes, and relationships.

-- Drop old tables to avoid conflicts and guarantee clean v2 schema installation
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS patient_statistics CASCADE;
DROP TABLE IF EXISTS disease_outbreaks CASCADE;
DROP TABLE IF EXISTS medicine_predictions CASCADE;
DROP TABLE IF EXISTS medicine_shortages CASCADE;
DROP TABLE IF EXISTS emergency_plans CASCADE;
DROP TABLE IF EXISTS medicine_transfers CASCADE;
DROP TABLE IF EXISTS medicine_requests CASCADE;
DROP TABLE IF EXISTS shortage_alerts CASCADE;
DROP TABLE IF EXISTS logistics_shipments CASCADE;
DROP TABLE IF EXISTS drivers CASCADE;
DROP TABLE IF EXISTS warehouse_inventory CASCADE;
DROP TABLE IF EXISTS warehouses CASCADE;
DROP TABLE IF EXISTS medicines CASCADE;

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Ensure PHCs table exists (references existing table structure)
CREATE TABLE IF NOT EXISTS phcs (
    "PHC_Code" VARCHAR(50) PRIMARY KEY,
    "PHC_Name" VARCHAR(255) NOT NULL,
    "District" VARCHAR(100) NOT NULL,
    "Population_Covered" INTEGER DEFAULT 15000,
    "Status" VARCHAR(50) DEFAULT 'Active'
);

-- 2. Create Warehouses Table
CREATE TABLE IF NOT EXISTS warehouses (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255)
);

-- 2.5 Create Warehouse Inventory Table
CREATE TABLE IF NOT EXISTS warehouse_inventory (
    id SERIAL PRIMARY KEY,
    warehouse_id VARCHAR(50) NOT NULL REFERENCES warehouses(id) ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0 CHECK (current_stock >= 0),
    unit VARCHAR(50) DEFAULT 'Units',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create Users Profile Table (linked to Supabase Auth.Users)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('PHC User', 'District Admin', 'State Admin', 'Warehouse Supervisor', 'Logistics Head')),
    phc_id VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE SET NULL,
    district VARCHAR(100),
    warehouse_id VARCHAR(50) REFERENCES warehouses(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create trigger function to automatically create profile on sign up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email, role, phc_id, district, warehouse_id)
  VALUES (
    new.id,
    new.email,
    COALESCE(new.raw_user_meta_data->>'role', 'PHC User'),
    new.raw_user_meta_data->>'phc_id',
    new.raw_user_meta_data->>'district',
    new.raw_user_meta_data->>'warehouse_id'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Bind trigger to auth.users table
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4. Create Logistics Shipments Table
CREATE TABLE IF NOT EXISTS logistics_shipments (
    id VARCHAR(50) PRIMARY KEY,
    vehicle_type VARCHAR(100) NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL,
    route VARCHAR(255) NOT NULL,
    source_warehouse_id VARCHAR(50) REFERENCES warehouses(id) ON DELETE CASCADE,
    destination_phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    delivery_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    priority VARCHAR(50) DEFAULT 'Medium',
    road_condition VARCHAR(50) DEFAULT 'Good',
    estimated_hours INTEGER DEFAULT 4,
    status VARCHAR(50) DEFAULT 'Scheduled' CHECK (status IN ('Scheduled', 'En Route', 'Delivered', 'Cancelled')),
    fuel_level INTEGER DEFAULT 100 CHECK (fuel_level BETWEEN 0 AND 100),
    battery_health INTEGER DEFAULT 100 CHECK (battery_health BETWEEN 0 AND 100),
    engine_status VARCHAR(50) DEFAULT 'Healthy',
    route_waypoints TEXT
);

-- 2.8 Create Drivers Table
CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    license_number VARCHAR(100) UNIQUE,
    status VARCHAR(50) DEFAULT 'Available', -- 'Available', 'On Trip', 'Off Duty'
    assigned_vehicle_id VARCHAR(50)
);

-- 3. Re-create/Ensure Inventory Table exists
-- We use a simplified inventory table referencing medicine name, batch, stock, unit, and expiry.
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    batch_number VARCHAR(100),
    current_stock INTEGER NOT NULL DEFAULT 0,
    unit VARCHAR(50) DEFAULT 'Units',
    expiry_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Patient Statistics Table
CREATE TABLE IF NOT EXISTS patient_statistics (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    total_patients INTEGER NOT NULL DEFAULT 0,
    male_patients INTEGER DEFAULT 0,
    female_patients INTEGER DEFAULT 0,
    children INTEGER DEFAULT 0,
    senior_citizens INTEGER DEFAULT 0,
    recorded_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Create Disease Outbreaks Table
CREATE TABLE IF NOT EXISTS disease_outbreaks (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    disease_category VARCHAR(100) NOT NULL,
    cases_reported INTEGER NOT NULL DEFAULT 0,
    recorded_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Create Medicine Predictions Table (AI demand forecasting results)
CREATE TABLE IF NOT EXISTS medicine_predictions (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    predicted_demand INTEGER NOT NULL DEFAULT 0,
    confidence_pct DOUBLE PRECISION DEFAULT 90.0,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Create Medicine Shortages Table (AI stockout warnings)
CREATE TABLE IF NOT EXISTS medicine_shortages (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    current_stock INTEGER NOT NULL DEFAULT 0,
    daily_consumption INTEGER NOT NULL DEFAULT 0,
    days_remaining DOUBLE PRECISION NOT NULL DEFAULT 999.0,
    risk_level VARCHAR(50) NOT NULL CHECK (risk_level IN ('Critical', 'High', 'Medium', 'Low')),
    estimated_stockout DATE,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Create Emergency Response Plans Table (AI responses)
CREATE TABLE IF NOT EXISTS emergency_plans (
    id SERIAL PRIMARY KEY,
    phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    disease VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    critical_medicines JSONB DEFAULT '[]'::jsonb,
    recommended_vehicle VARCHAR(100),
    response_hours INTEGER DEFAULT 12,
    action VARCHAR(255) DEFAULT 'STANDBY',
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Create Medicine Transfers Table (AI stock redistribution recommendations)
CREATE TABLE IF NOT EXISTS medicine_transfers (
    id SERIAL PRIMARY KEY,
    source_phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    destination_phc_id VARCHAR(50) NOT NULL REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    priority VARCHAR(50) DEFAULT 'Medium',
    road_condition VARCHAR(100) DEFAULT 'Good',
    transport_time INTEGER DEFAULT 4,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ─── SYSTEM INDEXES FOR OPTIMIZED QUERY SPEED ───
CREATE INDEX IF NOT EXISTS idx_inventory_phc ON inventory (phc_id);
CREATE INDEX IF NOT EXISTS idx_inventory_medicine ON inventory (medicine_name);
CREATE INDEX IF NOT EXISTS idx_patient_stats_phc ON patient_statistics (phc_id, recorded_date);
CREATE INDEX IF NOT EXISTS idx_outbreaks_phc ON disease_outbreaks (phc_id, recorded_date);
CREATE INDEX IF NOT EXISTS idx_predictions_phc ON medicine_predictions (phc_id);
CREATE INDEX IF NOT EXISTS idx_shortages_phc ON medicine_shortages (phc_id);
CREATE INDEX IF NOT EXISTS idx_transfers_source ON medicine_transfers (source_phc_id);
CREATE INDEX IF NOT EXISTS idx_transfers_dest ON medicine_transfers (destination_phc_id);

-- Disable Row Level Security on all tables to allow client-side and server-side anonymous operations
ALTER TABLE phcs DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE inventory DISABLE ROW LEVEL SECURITY;
ALTER TABLE patient_statistics DISABLE ROW LEVEL SECURITY;
ALTER TABLE disease_outbreaks DISABLE ROW LEVEL SECURITY;
ALTER TABLE medicine_predictions DISABLE ROW LEVEL SECURITY;
ALTER TABLE medicine_shortages DISABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_plans DISABLE ROW LEVEL SECURITY;
ALTER TABLE medicine_transfers DISABLE ROW LEVEL SECURITY;
ALTER TABLE warehouses DISABLE ROW LEVEL SECURITY;
ALTER TABLE logistics_shipments DISABLE ROW LEVEL SECURITY;
ALTER TABLE warehouse_inventory DISABLE ROW LEVEL SECURITY;
ALTER TABLE drivers DISABLE ROW LEVEL SECURITY;

-- Enable Realtime subscriptions on crucial tables (inventory, statistics, and calculations)
ALTER PUBLICATION supabase_realtime ADD TABLE inventory;
ALTER PUBLICATION supabase_realtime ADD TABLE patient_statistics;
ALTER PUBLICATION supabase_realtime ADD TABLE disease_outbreaks;
ALTER PUBLICATION supabase_realtime ADD TABLE medicine_predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE medicine_shortages;
ALTER PUBLICATION supabase_realtime ADD TABLE medicine_transfers;
ALTER PUBLICATION supabase_realtime ADD TABLE emergency_plans;
ALTER PUBLICATION supabase_realtime ADD TABLE logistics_shipments;
ALTER PUBLICATION supabase_realtime ADD TABLE warehouse_inventory;
ALTER PUBLICATION supabase_realtime ADD TABLE drivers;

-- Grant full read/write privileges on all tables, sequences, and functions to anon and authenticated roles
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, postgres, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, postgres, service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon, authenticated, postgres, service_role;
