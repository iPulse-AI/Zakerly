-- Migration to fix foreign key constraint for book deletion
-- This allows cascade deletion of chat sessions when a book is deleted

-- First, drop the existing foreign key constraint
ALTER TABLE chat_sessions DROP CONSTRAINT IF EXISTS fk_book;

-- Add the new foreign key constraint with CASCADE DELETE
ALTER TABLE chat_sessions ADD CONSTRAINT fk_book
    FOREIGN KEY (book_id)
    REFERENCES books(id)
    ON DELETE CASCADE;

-- Verify the constraint was added properly
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.delete_rule
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
    JOIN information_schema.referential_constraints AS rc
      ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
    AND tc.table_name = 'chat_sessions'
    AND kcu.column_name = 'book_id';
