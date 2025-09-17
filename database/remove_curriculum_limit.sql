-- Remove curriculum limit restriction
-- This script removes the maximum 5 curriculum limit

-- Drop the trigger that enforces curriculum limit
DROP TRIGGER IF EXISTS curriculum_limit_trigger ON curriculum;

-- Drop the function that checks curriculum limit
DROP FUNCTION IF EXISTS check_curriculum_limit();

-- Success message
SELECT 'Curriculum limit restriction removed successfully' as message;
