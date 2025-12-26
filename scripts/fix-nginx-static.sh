#!/bin/bash
# Fix Nginx static files path to use Docker volume
# Usage: sudo ./scripts/fix-nginx-static.sh

set -e

echo "==========================================="
echo "Fix Nginx Static Files Path"
echo "==========================================="
echo ""

NGINX_CONF="/etc/nginx/sites-enabled/eatfit24.ru"
STATIC_VOLUME="/var/lib/docker/volumes/eatfit24-backend-static/_data"
MEDIA_VOLUME="/var/lib/docker/volumes/eatfit24-backend-media/_data"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo $0"
    exit 1
fi

# Backup current config
echo ">>> Creating backup of Nginx config..."
cp "$NGINX_CONF" "$NGINX_CONF.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ Backup created"
echo ""

# Update static path
echo ">>> Updating static files path..."
sed -i "s|alias /opt/EatFit24/backend/staticfiles/;|alias $STATIC_VOLUME/;|g" "$NGINX_CONF"
echo "✅ Static path updated to Docker volume"
echo ""

# Update media path (if needed)
echo ">>> Updating media files path..."
if grep -q "alias /opt/EatFit24/backend/media/" "$NGINX_CONF"; then
    sed -i "s|alias /opt/EatFit24/backend/media/;|alias $MEDIA_VOLUME/;|g" "$NGINX_CONF"
    echo "✅ Media path updated to Docker volume"
else
    echo "ℹ️  Media path already correct"
fi
echo ""

# Test Nginx config
echo ">>> Testing Nginx configuration..."
nginx -t
echo "✅ Nginx config is valid"
echo ""

# Reload Nginx
echo ">>> Reloading Nginx..."
systemctl reload nginx
echo "✅ Nginx reloaded"
echo ""

echo "==========================================="
echo "Summary"
echo "==========================================="
echo "Static files: $STATIC_VOLUME"
echo "Media files:  $MEDIA_VOLUME"
echo ""
echo "Next steps:"
echo "  1. Test admin panel: https://eatfit24.ru/dj-admin/login/"
echo "  2. Check static files load correctly"
echo ""
