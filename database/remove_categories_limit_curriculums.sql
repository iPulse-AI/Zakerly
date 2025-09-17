-- Migration script to remove categories and limit curriculums
-- This script removes all category logic and limits curriculums to 5

-- Step 1: Remove category_id from books table
ALTER TABLE books DROP CONSTRAINT IF EXISTS fk_category;
ALTER TABLE books DROP COLUMN IF EXISTS category_id;

-- Step 2: Drop category table completely
DROP TABLE IF EXISTS category CASCADE;

-- Step 3: Remove category index
DROP INDEX IF EXISTS idx_books_category_id;

-- Step 4: Delete system curriculums and keep only 5
DELETE FROM curriculum WHERE created_by = 'system';

-- Step 5: Insert only 5 essential curriculums
INSERT INTO curriculum (name, description, created_by) VALUES 
    ('Computer Science', 'Computer science, programming, and technology', 'user'),
    ('Mathematics', 'Mathematics and related mathematical concepts', 'user'),
    ('Science', 'General science and scientific principles', 'user'),
    ('Business', 'Business, economics, and management', 'user'),
    ('General Studies', 'General academic content and miscellaneous topics', 'user')
ON CONFLICT (name) DO NOTHING;

-- Step 6: Create a constraint to limit curriculums to maximum 5
CREATE OR REPLACE FUNCTION check_curriculum_limit()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM curriculum) >= 5 THEN
        RAISE EXCEPTION 'Maximum of 5 curriculums allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER curriculum_limit_trigger
    BEFORE INSERT ON curriculum
    FOR EACH ROW EXECUTE FUNCTION check_curriculum_limit();

-- Step 7: Create embedding tables for the 5 curriculums
DO $$
DECLARE
    curr RECORD;
BEGIN
    FOR curr IN SELECT name FROM curriculum LOOP
        PERFORM create_curriculum_embedding_table(curr.name, 1536);
    END LOOP;
END $$;

-- Step 8: Update books table to make curriculum_id NOT NULL and required
ALTER TABLE books ALTER COLUMN curriculum_id SET NOT NULL;

-- Step 9: Add check constraint to ensure all books have curriculum_id
ALTER TABLE books ADD CONSTRAINT check_curriculum_required 
    CHECK (curriculum_id IS NOT NULL);
