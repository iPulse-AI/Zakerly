#!/bin/bash

echo "🔍 LANGCHAIN_ZAKERLY - Post-Refactoring Verification"
echo "=================================================="
echo

# Check if all containers are running
echo "📊 Container Status:"
docker compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"
echo

# Test frontend accessibility
echo "🌐 Testing Frontend Accessibility:"
frontend_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)
if [ "$frontend_status" = "200" ]; then
    echo "✅ Frontend (localhost:3000): ACCESSIBLE"
else
    echo "❌ Frontend (localhost:3000): NOT ACCESSIBLE (HTTP $frontend_status)"
fi

# Test API Gateway
echo "🔗 Testing API Gateway:"
api_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
if [ "$api_status" = "200" ]; then
    echo "✅ API Gateway (localhost:8000): ACCESSIBLE"
else
    echo "❌ API Gateway (localhost:8000): NOT ACCESSIBLE (HTTP $api_status)"
fi

# Check frontend logs for any errors
echo
echo "📋 Recent Frontend Logs:"
echo "------------------------"
docker compose logs --tail=10 frontend

echo
echo "🎉 Refactoring Verification Complete!"
echo
echo "📱 Access Points:"
echo "   Frontend:     http://localhost:3000"
echo "   API Gateway:  http://localhost:8000"
echo "   pgAdmin:      http://localhost:8080"
echo "   Prometheus:   http://localhost:9090"
echo "   Grafana:      http://localhost:3001"
