-- Update lecture_scripts scope constraint to support curriculum-based scope types
-- Date: 2025-09-18
-- Description: Add support for 'whole_curriculum' and 'specific_book' scope types

-- Drop the old constraint
ALTER TABLE lecture_scripts DROP CONSTRAINT IF EXISTS lecture_scripts_scope_check;

-- Add the updated constraint with new scope values
ALTER TABLE lecture_scripts 
ADD CONSTRAINT lecture_scripts_scope_check 
CHECK (scope IN ('whole_book', 'specific_topics', 'whole_curriculum', 'specific_book'));

-- Verify the constraint
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE conrelid = 'lecture_scripts'::regclass 
AND contype = 'c' 
AND conname = 'lecture_scripts_scope_check';
