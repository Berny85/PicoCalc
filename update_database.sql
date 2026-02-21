-- Migration: Neue Spalten für Tintenstrahl-Drucker hinzufügen
-- PicoCalc Database Update

-- Neue Spalten zur machines Tabelle hinzufügen
ALTER TABLE machines 
    ADD COLUMN IF NOT EXISTS lifespan_pages NUMERIC(10, 0),
    ADD COLUMN IF NOT EXISTS depreciation_per_page NUMERIC(10, 4);

-- Verifizierung
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'machines' 
ORDER BY ordinal_position;
