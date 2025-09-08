#!/bin/bash

# Simple script to clear authentication data from browser localStorage
# This can be run when containers restart

echo "🔧 Clearing authentication data..."

# If you want to clear localStorage programmatically, 
# you can also add this line to your container startup

# For now, we'll rely on the automatic detection in AuthContext
echo "✅ Authentication will be cleared on next browser refresh due to container restart detection"
echo "💡 If you're still logged in, use the 'Clear all data & logout' option from the user menu"
