-- Migration script to update vendor IDs from PMC/LOGI/VEN001 to PMC-LOGI-VEN001
-- This fixes URL routing issues caused by slashes in vendor IDs

-- Update all existing vendor IDs to use hyphens instead of slashes
UPDATE vendors
SET vendor_id = REPLACE(vendor_id, '/', '-')
WHERE vendor_id LIKE 'PMC/LOGI/%';

-- Verify the update
SELECT vendor_id, organization_name, status, approval_status
FROM vendors
ORDER BY created_at DESC;
