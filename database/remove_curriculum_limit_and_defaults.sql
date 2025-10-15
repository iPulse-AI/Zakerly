-- Remove curriculum limit and default curriculums
-- This script removes the 5-curriculum limit and deletes the default curriculums

-- Start transaction for safety
BEGIN;

-- Step 1: Remove the curriculum limit trigger and function
DROP TRIGGER IF EXISTS curriculum_limit_trigger ON curriculum;
DROP FUNCTION IF EXISTS check_curriculum_limit();

-- Step 2: Get curriculum IDs to remove (store them for cascading deletes)
CREATE TEMP TABLE curricula_to_remove AS
SELECT id FROM curriculum 
WHERE name IN ('Law', 'Medical', 'IT', 'Business', 'Engineering');

-- Step 3: Remove curriculum-specific embedding tables (if they exist)
-- Note: These tables might have curriculum-specific names
DROP TABLE IF EXISTS curriculum_embeddings_law CASCADE;
DROP TABLE IF EXISTS curriculum_embeddings_medical CASCADE;
DROP TABLE IF EXISTS curriculum_embeddings_it CASCADE;
DROP TABLE IF EXISTS curriculum_embeddings_business CASCADE;
DROP TABLE IF EXISTS curriculum_embeddings_engineering CASCADE;

-- Step 4: Remove books associated with these curriculums
-- This will cascade to remove associated embeddings, chat sessions, etc.
DELETE FROM books WHERE curriculum_id IN (SELECT id FROM curricula_to_remove);

-- Step 5: Remove any chat sessions associated with these curriculums
DELETE FROM chat_sessions WHERE curriculum_name IN ('Law', 'Medical', 'IT', 'Business', 'Engineering');

-- Step 6: Remove any other curriculum-related data
DELETE FROM questions WHERE curriculum_id IN (SELECT id FROM curricula_to_remove);
DELETE FROM lecture_scripts WHERE curriculum_id IN (SELECT id FROM curricula_to_remove);

-- Step 7: Remove the curriculums themselves
DELETE FROM curriculum WHERE id IN (SELECT id FROM curricula_to_remove);

-- Step 8: Clean up temp table
DROP TABLE curricula_to_remove;

-- Step 9: Verify removal
SELECT 'Remaining curriculums:' as status;
SELECT id, name, description FROM curriculum;

SELECT 'Curriculum limit function status:' as status;
SELECT CASE 
    WHEN EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'check_curriculum_limit') 
    THEN 'Function still exists' 
    ELSE 'Function removed successfully' 
END as function_status;

SELECT 'Curriculum limit trigger status:' as status;
SELECT CASE 
    WHEN EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'curriculum_limit_trigger') 
    THEN 'Trigger still exists' 
    ELSE 'Trigger removed successfully' 
END as trigger_status;

-- Commit the transaction
COMMIT;

-- Show completion message
SELECT 'Curriculum limit and default curriculums removed successfully!' as result;