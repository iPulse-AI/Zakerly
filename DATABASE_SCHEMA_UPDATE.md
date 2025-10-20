# Database Schema Update - October 19, 2025

## Changes Made

### 1. **Presentations Table Added to init.sql**
   - Merged `add_presentations_table.sql` into main `init.sql`
   - Removed separate migration file
   - Table now created automatically on fresh database initialization

### 2. **Lecture Scripts Table Updated**
   - `book_id` changed from `NOT NULL` to nullable
   - Added `whole_curriculum` to scope CHECK constraint
   - Allows scripts for entire curriculum, not just individual books

### 3. **New Presentations Table Schema**
   ```sql
   CREATE TABLE presentations (
       id UUID PRIMARY KEY,
       user_id UUID NOT NULL,
       book_id INTEGER,  -- nullable for curriculum-wide presentations
       title TEXT NOT NULL,
       scope TEXT CHECK (scope IN ('whole_curriculum', 'whole_book', 'specific_topics')),
       specific_topics TEXT,
       detail_level TEXT CHECK (detail_level IN ('overview', 'detailed', 'comprehensive')),
       difficulty TEXT CHECK (difficulty IN ('beginner', 'intermediate', 'advanced')),
       slides_count INTEGER DEFAULT 15 CHECK (slides_count >= 5 AND slides_count <= 50),
       slide_style TEXT DEFAULT 'professional' CHECK (slide_style IN ('professional', 'creative', 'minimal')),
       include_diagrams BOOLEAN DEFAULT true,
       include_code_examples BOOLEAN DEFAULT false,
       content JSONB NOT NULL,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

### 4. **Indexes Added**
   - `idx_presentations_user_id`
   - `idx_presentations_book_id`
   - `idx_presentations_created_at`
   - `idx_presentations_scope`
   - `idx_lecture_scripts_user_id`
   - `idx_lecture_scripts_book_id`

### 5. **Triggers Added**
   - `update_presentations_updated_at` - Auto-update timestamp on presentation updates
   - `update_lecture_scripts_updated_at` - Auto-update timestamp on script updates

## Migration Steps for Existing Databases

If you have an existing database, run these commands:

```bash
# 1. Run the presentations table creation manually (already done)
docker compose exec -T postgres psql -U zakerly_user -d zakerly_db < database/add_presentations_table.sql

# 2. Update lecture_scripts to allow null book_id
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "ALTER TABLE lecture_scripts ALTER COLUMN book_id DROP NOT NULL;"

# 3. Update lecture_scripts scope constraint
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "
ALTER TABLE lecture_scripts DROP CONSTRAINT lecture_scripts_scope_check;
ALTER TABLE lecture_scripts ADD CONSTRAINT lecture_scripts_scope_check 
  CHECK (scope IN ('whole_curriculum', 'whole_book', 'specific_topics'));
"
```

## For Fresh Installations

Simply run:
```bash
docker compose down -v  # Remove old data
docker compose up -d    # Start with fresh database
```

The `init.sql` will automatically create all tables including presentations.

## Verification

Check that everything is working:

```bash
# Verify presentations table exists
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "\d presentations"

# Verify lecture_scripts table updated
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "\d lecture_scripts"

# Test queries
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "SELECT COUNT(*) FROM presentations;"
docker compose exec postgres psql -U zakerly_user -d zakerly_db -c "SELECT COUNT(*) FROM lecture_scripts;"
```

## Services Affected

- ✅ **Presentation Service** - Now working properly
- ✅ **Script Service** - Updated to support curriculum-wide scripts
- ✅ **Frontend** - Presentations page now loads correctly

## Notes

- All changes are backward compatible
- Existing data is preserved
- New installations get everything automatically
- No code changes needed in services (they already expected these tables)
