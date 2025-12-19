-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Example: Create a table for raw inputs
CREATE TABLE IF NOT EXISTS raw_addresses (
    id SERIAL PRIMARY KEY,
    raw_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Example: Create a table for refined addresses
CREATE TABLE IF NOT EXISTS refined_addresses (
    id SERIAL PRIMARY KEY,
    raw_address_id INTEGER REFERENCES raw_addresses(id),
    refined_text TEXT,
    road_addr_part1 TEXT,
    road_addr_part2 TEXT,
    zip_no TEXT,
    emd_cd TEXT, -- Administrative code
    geom GEOMETRY(Point, 4326), -- Spatial location (Long, Lat)
    score FLOAT, -- Confidence score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
