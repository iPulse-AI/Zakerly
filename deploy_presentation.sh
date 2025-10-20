#!/bin/bash

echo "🎯 Deploying Presentation Feature..."
echo "======================================"

# Step 1: Apply database migration
echo ""
echo "📊 Step 1: Applying database migration..."
docker compose exec -T postgres psql -U zakerly_user -d zakerly_db << EOF
-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create presentations table
CREATE TABLE IF NOT EXISTS presentations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('whole_curriculum', 'whole_book', 'specific_topics')),
    specific_topics TEXT,
    detail_level TEXT NOT NULL CHECK (detail_level IN ('overview', 'detailed', 'comprehensive')),
    difficulty TEXT NOT NULL CHECK (difficulty IN ('beginner', 'intermediate', 'advanced')),
    slides_count INTEGER DEFAULT 10 CHECK (slides_count > 0 AND slides_count <= 100),
    slide_style TEXT DEFAULT 'professional' CHECK (slide_style IN ('professional', 'creative', 'minimal')),
    include_diagrams BOOLEAN DEFAULT true,
    include_code_examples BOOLEAN DEFAULT false,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_presentations_user_id ON presentations(user_id);
CREATE INDEX IF NOT EXISTS idx_presentations_book_id ON presentations(book_id);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_presentations_updated_at()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
\$\$ language 'plpgsql';

DROP TRIGGER IF EXISTS presentations_updated_at ON presentations;
CREATE TRIGGER presentations_updated_at
    BEFORE UPDATE ON presentations
    FOR EACH ROW
    EXECUTE FUNCTION update_presentations_updated_at();

EOF

if [ $? -eq 0 ]; then
    echo "✅ Database migration completed successfully"
else
    echo "❌ Database migration failed"
    exit 1
fi

# Step 2: Build presentation service
echo ""
echo "🔨 Step 2: Building presentation service..."
docker compose build presentation-service

if [ $? -eq 0 ]; then
    echo "✅ Build completed successfully"
else
    echo "❌ Build failed"
    exit 1
fi

# Step 3: Start presentation service
echo ""
echo "🚀 Step 3: Starting presentation service..."
docker compose up -d presentation-service

if [ $? -eq 0 ]; then
    echo "✅ Service started successfully"
else
    echo "❌ Service start failed"
    exit 1
fi

# Step 4: Restart gateway
echo ""
echo "🔄 Step 4: Restarting gateway..."
docker compose restart gateway

if [ $? -eq 0 ]; then
    echo "✅ Gateway restarted successfully"
else
    echo "❌ Gateway restart failed"
    exit 1
fi

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Step 5: Verify deployment
echo ""
echo "🔍 Step 5: Verifying deployment..."
echo ""

echo "Checking presentation service logs:"
docker compose logs --tail=20 presentation-service

echo ""
echo "======================================"
echo "✅ Deployment Complete!"
echo ""
echo "Services:"
echo "  - Presentation Service: http://localhost:8005"
echo "  - Gateway: http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo ""
echo "Next steps:"
echo "  1. Navigate to http://localhost:5173/presentations"
echo "  2. Generate your first presentation"
echo "  3. View and present your slides"
echo ""
echo "Happy presenting! 🎉"
