-- Update lecture_scripts table to support curriculum-based scripts
-- This script will modify the existing table to support both curriculum and book-based scripts

-- First, let's modify the table structure
ALTER TABLE lecture_scripts 
    ALTER COLUMN book_id DROP NOT NULL,
    ADD COLUMN curriculum_id INTEGER,
    ADD COLUMN script_style VARCHAR(50) DEFAULT 'lecture',
    ADD COLUMN target_audience VARCHAR(50) DEFAULT 'intermediate',
    ADD COLUMN specific_books TEXT,
    ADD COLUMN include_examples BOOLEAN DEFAULT true,
    ADD COLUMN include_exercises BOOLEAN DEFAULT false,
    ADD COLUMN include_visual_aids BOOLEAN DEFAULT true;

-- Update the scope constraint to include curriculum scopes
ALTER TABLE lecture_scripts 
    DROP CONSTRAINT IF EXISTS lecture_scripts_scope_check;

ALTER TABLE lecture_scripts 
    ADD CONSTRAINT lecture_scripts_scope_check 
    CHECK (scope IN ('whole_curriculum', 'whole_book', 'specific_topics'));

-- Add foreign key constraint for curriculum_id
ALTER TABLE lecture_scripts 
    ADD CONSTRAINT fk_script_curriculum
    FOREIGN KEY (curriculum_id)
    REFERENCES curriculum(id) ON DELETE CASCADE;

-- Add constraint to ensure either curriculum_id or book_id is provided
ALTER TABLE lecture_scripts 
    ADD CONSTRAINT check_curriculum_or_book 
    CHECK (curriculum_id IS NOT NULL OR book_id IS NOT NULL);

-- Create index for curriculum_id
CREATE INDEX IF NOT EXISTS idx_lecture_scripts_curriculum_id ON lecture_scripts(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_lecture_scripts_user_id ON lecture_scripts(user_id);
CREATE INDEX IF NOT EXISTS idx_lecture_scripts_created_at ON lecture_scripts(created_at);

-- Add trigger for lecture_scripts updated_at
CREATE TRIGGER update_lecture_scripts_updated_at 
    BEFORE UPDATE ON lecture_scripts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();