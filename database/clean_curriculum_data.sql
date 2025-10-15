-- Simple script to clean curriculum data
BEGIN;

-- Remove any existing default curriculums
DELETE FROM curriculum WHERE name IN ('Law', 'Medical', 'IT', 'Business', 'Engineering');

-- Show remaining curriculums
SELECT COUNT(*) as remaining_curriculums FROM curriculum;

COMMIT;

SELECT 'Default curriculums removed successfully!' as result;