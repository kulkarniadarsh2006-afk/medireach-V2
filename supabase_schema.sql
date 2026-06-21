-- 1. Create medicines table
CREATE TABLE IF NOT EXISTS medicines (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    unit VARCHAR(50),
    critical BOOLEAN DEFAULT FALSE
);

-- 2. Create warehouses table
CREATE TABLE IF NOT EXISTS warehouses (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255)
);

-- 3. Create inventory table
CREATE TABLE IF NOT EXISTS inventory (
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    stock INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (phc_code, medicine_id)
);

-- 4. Create disease_outbreaks table
CREATE TABLE IF NOT EXISTS disease_outbreaks (
    id SERIAL PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    disease VARCHAR(100) NOT NULL,
    affected INTEGER NOT NULL DEFAULT 0,
    severity VARCHAR(50) NOT NULL, -- 'Low', 'Medium', 'High', 'Critical'
    spread_rate DOUBLE PRECISION DEFAULT 1.0,
    started DATE NOT NULL DEFAULT CURRENT_DATE
);

-- 5. Create shortage_alerts table
CREATE TABLE IF NOT EXISTS shortage_alerts (
    id SERIAL PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    current_stock INTEGER NOT NULL,
    daily_consumption INTEGER NOT NULL,
    days_remaining DOUBLE PRECISION NOT NULL,
    risk_level VARCHAR(50) NOT NULL,
    estimated_stockout DATE NOT NULL,
    action_required VARCHAR(255),
    outbreak_linked VARCHAR(100),
    weather_alert VARCHAR(100)
);

-- 6. Create medicine_requests table
CREATE TABLE IF NOT EXISTS medicine_requests (
    id SERIAL PRIMARY KEY,
    phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending', -- 'Pending', 'Approved', 'Dispatched', 'Completed'
    priority VARCHAR(50) DEFAULT 'Medium', -- 'Low', 'Medium', 'High', 'Critical'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Create logistics_shipments table
CREATE TABLE IF NOT EXISTS logistics_shipments (
    id VARCHAR(50) PRIMARY KEY,
    vehicle_type VARCHAR(100) NOT NULL,
    vehicle_id VARCHAR(50) NOT NULL,
    route VARCHAR(255) NOT NULL,
    source_warehouse_id VARCHAR(50) REFERENCES warehouses(id) ON DELETE CASCADE,
    destination_phc_code VARCHAR(50) REFERENCES phcs("PHC_Code") ON DELETE CASCADE,
    medicine_id VARCHAR(50) REFERENCES medicines(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    delivery_time TIMESTAMP WITH TIME ZONE NOT NULL,
    priority VARCHAR(50) NOT NULL,
    road_condition VARCHAR(50) NOT NULL,
    estimated_hours INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'Scheduled' -- 'Scheduled', 'En Route', 'Delivered', 'Cancelled'
);
