-- SQL Schema Fixes for MediReach Unified Platform
-- Copy and execute these queries in your Supabase SQL Editor.

-- 1. Create users table for role-based authentication and settings
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    email VARCHAR(100) UNIQUE,
    mobile VARCHAR(20) UNIQUE,
    role VARCHAR(50) NOT NULL, -- 'PHC User', 'District Admin', 'State Admin', 'Transport Coordinator'
    phc_code VARCHAR(50),
    phc_name VARCHAR(255),
    district VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Create patient_statistics table for local PHC Patient logging
CREATE TABLE IF NOT EXISTS patient_statistics (
    id SERIAL PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    opd_patients_total INTEGER DEFAULT 0,
    opd_new_cases INTEGER DEFAULT 0,
    opd_referred_cases INTEGER DEFAULT 0,
    opd_immunizations INTEGER DEFAULT 0,
    recorded_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Create medicine_demand_predictions table for AI-driven inventory forecasting
CREATE TABLE IF NOT EXISTS medicine_demand_predictions (
    id SERIAL PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    days INTEGER NOT NULL,
    predicted_demand INTEGER NOT NULL,
    confidence_pct DOUBLE PRECISION DEFAULT 90.0,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create deliveries table for vehicle/delivery tracking and logistics management
CREATE TABLE IF NOT EXISTS deliveries (
    id SERIAL PRIMARY KEY,
    vehicle_id VARCHAR(50) NOT NULL,
    vehicle_type VARCHAR(100) NOT NULL,
    route VARCHAR(255) NOT NULL,
    destination_phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'Scheduled', -- 'Scheduled', 'En Route', 'Delivered', 'Cancelled'
    delivery_time TIMESTAMP WITH TIME ZONE,
    priority VARCHAR(50) DEFAULT 'Medium',
    road_condition VARCHAR(50) DEFAULT 'Good',
    estimated_hours INTEGER DEFAULT 4,
    fuel_status VARCHAR(50) DEFAULT 'Full', -- 'Full', 'Half', 'Low', 'Critical'
    gps_latitude DOUBLE PRECISION,
    gps_longitude DOUBLE PRECISION,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Modify inventory table to include batch_number column for tracking
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS batch_number VARCHAR(100);

-- 6. Modify disease_outbreaks table to include disease_category and cases_reported columns
ALTER TABLE disease_outbreaks ADD COLUMN IF NOT EXISTS disease_category VARCHAR(100);
ALTER TABLE disease_outbreaks ADD COLUMN IF NOT EXISTS cases_reported INTEGER DEFAULT 0;

-- 7. Ensure rhim_sync_log table is fully configured as fallback for sync records
CREATE TABLE IF NOT EXISTS rhim_sync_log (
    sync_id VARCHAR(100) PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    phc_name VARCHAR(255),
    district VARCHAR(100),
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sync_source VARCHAR(100) DEFAULT 'PHC-Portal',
    inventory_items_received INTEGER DEFAULT 0,
    inventory_total_units INTEGER DEFAULT 0,
    inventory_critical_items INTEGER DEFAULT 0,
    disease_reports_received INTEGER DEFAULT 0,
    disease_cases_total INTEGER DEFAULT 0,
    disease_alerts INTEGER DEFAULT 0,
    opd_patients_total INTEGER DEFAULT 0,
    opd_new_cases INTEGER DEFAULT 0,
    opd_referred_cases INTEGER DEFAULT 0,
    opd_immunizations INTEGER DEFAULT 0,
    inventory_payload TEXT,
    disease_payload TEXT,
    opd_payload TEXT,
    sync_status VARCHAR(50) DEFAULT 'completed'
);
