-- Migration script to implement Enhanced Curriculum System (Option A)
-- This replaces the category-based system with a dynamic curriculum system

BEGIN;

-- Step 1: Create curriculum table
CREATE TABLE IF NOT EXISTS curriculum (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_by VARCHAR(255) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for curriculum name
CREATE INDEX IF NOT EXISTS idx_curriculum_name ON curriculum(name);
CREATE INDEX IF NOT EXISTS idx_curriculum_created_by ON curriculum(created_by);

-- Step 2: Insert default curriculums
INSERT INTO curriculum (name, description, created_by) VALUES 
    ('Mathematics', 'Mathematics and related mathematical concepts', 'system'),
    ('Science', 'General science and scientific principles', 'system'),
    ('Physics', 'Physics and physical sciences', 'system'),
    ('Chemistry', 'Chemistry and chemical sciences', 'system'),
    ('History', 'History and historical studies', 'system'),
    ('Geology', 'Geology and earth sciences', 'system'),
    ('Computer Science', 'Computer science, programming, and technology', 'system'),
    ('Literature', 'Literature, language arts, and writing', 'system'),
    ('Business', 'Business, economics, and management', 'system'),
    ('Psychology', 'Psychology and behavioral sciences', 'system'),
    ('Biology', 'Biology and life sciences', 'system'),
    ('Engineering', 'Engineering and technical disciplines', 'system'),
    ('Medicine', 'Medical and health sciences', 'system'),
    ('Law', 'Legal studies and jurisprudence', 'system'),
    ('General Studies', 'General academic content and miscellaneous topics', 'system')
ON CONFLICT (name) DO NOTHING;

-- Step 3: Add curriculum_id column to books table
ALTER TABLE books ADD COLUMN IF NOT EXISTS curriculum_id INTEGER;

-- Add foreign key constraint to curriculum table
ALTER TABLE books ADD CONSTRAINT fk_curriculum
    FOREIGN KEY (curriculum_id)
    REFERENCES curriculum(id);

-- Step 4: Create curriculum_embeddings table (one per curriculum approach)
-- This is a template - actual tables will be created dynamically per curriculum
CREATE TABLE IF NOT EXISTS curriculum_embeddings_template (
    id SERIAL PRIMARY KEY,
    curriculum_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1536), -- Default dimension, will be adjusted based on actual embeddings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_curriculum_embeddings_curriculum
        FOREIGN KEY (curriculum_id)
        REFERENCES curriculum(id) ON DELETE CASCADE,
    CONSTRAINT fk_curriculum_embeddings_book
        FOREIGN KEY (book_id)
        REFERENCES books(id) ON DELETE CASCADE
);

-- Create indexes for curriculum_embeddings_template
CREATE INDEX IF NOT EXISTS idx_curriculum_embeddings_curriculum_id ON curriculum_embeddings_template(curriculum_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_embeddings_book_id ON curriculum_embeddings_template(book_id);

-- Step 5: Migrate existing books to curriculum system (map from categories to curriculums)
UPDATE books SET curriculum_id = (
    CASE 
        WHEN category_id = 1 THEN (SELECT id FROM curriculum WHERE name = 'Mathematics')
        WHEN category_id = 2 THEN (SELECT id FROM curriculum WHERE name = 'Science')
        WHEN category_id = 3 THEN (SELECT id FROM curriculum WHERE name = 'Physics')
        WHEN category_id = 4 THEN (SELECT id FROM curriculum WHERE name = 'Chemistry')
        WHEN category_id = 5 THEN (SELECT id FROM curriculum WHERE name = 'History')
        WHEN category_id = 6 THEN (SELECT id FROM curriculum WHERE name = 'Geology')
        WHEN category_id = 7 THEN (SELECT id FROM curriculum WHERE name = 'General Studies')
        ELSE (SELECT id FROM curriculum WHERE name = 'General Studies')
    END
) WHERE curriculum_id IS NULL AND category_id IS NOT NULL;

-- Set default curriculum for any books without category_id
UPDATE books SET curriculum_id = (SELECT id FROM curriculum WHERE name = 'General Studies')
WHERE curriculum_id IS NULL;

-- Step 6: Make curriculum_id NOT NULL after data migration
ALTER TABLE books ALTER COLUMN curriculum_id SET NOT NULL;

-- Step 7: Create index for books.curriculum_id
CREATE INDEX IF NOT EXISTS idx_books_curriculum_id ON books(curriculum_id);

-- Step 8: Create function to create curriculum-specific embedding tables
CREATE OR REPLACE FUNCTION create_curriculum_embedding_table(curriculum_name TEXT, embedding_dimension INTEGER DEFAULT 1536)
RETURNS TEXT AS $$
DECLARE
    table_name TEXT;
    safe_name TEXT;
BEGIN
    -- Create safe table name from curriculum name
    safe_name := regexp_replace(lower(curriculum_name), '[^a-z0-9_]', '_', 'g');
    safe_name := regexp_replace(safe_name, '_+', '_', 'g');
    safe_name := trim(safe_name, '_');
    table_name := 'curriculum_embeddings_' || safe_name;
    
    -- Create the table with dynamic embedding dimension
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I (
            id SERIAL PRIMARY KEY,
            curriculum_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding vector(%s),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_%I_curriculum
                FOREIGN KEY (curriculum_id)
                REFERENCES curriculum(id) ON DELETE CASCADE,
            CONSTRAINT fk_%I_book
                FOREIGN KEY (book_id)
                REFERENCES books(id) ON DELETE CASCADE
        )', table_name, embedding_dimension, table_name, table_name);
    
    -- Create indexes
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_curriculum_id ON %I(curriculum_id)', table_name, table_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_book_id ON %I(book_id)', table_name, table_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_embedding ON %I USING ivfflat (embedding vector_cosine_ops)', table_name, table_name);
    
    RETURN table_name;
END;
$$ LANGUAGE plpgsql;

-- Step 9: Create function to get curriculum embedding table name
CREATE OR REPLACE FUNCTION get_curriculum_embedding_table_name(curriculum_name TEXT)
RETURNS TEXT AS $$
DECLARE
    safe_name TEXT;
BEGIN
    safe_name := regexp_replace(lower(curriculum_name), '[^a-z0-9_]', '_', 'g');
    safe_name := regexp_replace(safe_name, '_+', '_', 'g');
    safe_name := trim(safe_name, '_');
    RETURN 'curriculum_embeddings_' || safe_name;
END;
$$ LANGUAGE plpgsql;

-- Step 10: Create triggers for curriculum table
CREATE OR REPLACE FUNCTION update_curriculum_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_curriculum_updated_at 
    BEFORE UPDATE ON curriculum 
    FOR EACH ROW EXECUTE FUNCTION update_curriculum_updated_at();

-- Step 11: Create default embedding tables for existing curriculums
DO $$
DECLARE
    curr RECORD;
BEGIN
    FOR curr IN SELECT name FROM curriculum LOOP
        PERFORM create_curriculum_embedding_table(curr.name, 1536);
    END LOOP;
END $$;

-- Note: We keep the old category table for backward compatibility during migration
-- It can be removed in a future migration once everything is verified to work
-- ALTER TABLE books DROP COLUMN category_id;
-- DROP TABLE category;

COMMIT;
