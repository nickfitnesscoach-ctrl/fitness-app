server {
    listen 80;
    server_name eatfit24.ru www.eatfit24.ru;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name eatfit24.ru www.eatfit24.ru;

    ssl_certificate /etc/letsencrypt/live/eatfit24.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eatfit24.ru/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    # Note: X-XSS-Protection removed (deprecated, modern browsers ignore it)

    # Max upload size for avatars
    client_max_body_size 10M;

    # Static files (served by WhiteNoise via Django)
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Media files (served directly by Nginx from bind mount)
    location /media/ {
        alias /opt/eatfit24/media/;
        try_files $uri =404;
        access_log off;
        expires 30d;
        add_header Cache-Control "public";
    }

    # Health checks (proxy to backend)
    location ~ ^/(health|ready|live)/$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Django Admin (dj-admin)
    location /dj-admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Django Backend API - AI endpoints (long timeouts, ^~ for priority)
    location ^~ /api/v1/ai/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        # Telegram auth header (SSOT: backend expects X-Telegram-Init-Data)
        proxy_set_header X-Telegram-Init-Data $http_x_telegram_init_data;

        # AI recognition can take up to 2 minutes
        proxy_connect_timeout 150s;
        proxy_send_timeout 150s;
        proxy_read_timeout 150s;
    }

    # Django Backend API - all other endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        # Telegram auth header (SSOT: backend expects X-Telegram-Init-Data)
        proxy_set_header X-Telegram-Init-Data $http_x_telegram_init_data;

        # Standard timeouts (60s read for reports/exports)
        proxy_connect_timeout 15s;
        proxy_send_timeout 30s;
        proxy_read_timeout 60s;
    }

    # Frontend (React) - must be last
    # Note: For proper WebSocket keep-alive, add to nginx.conf http{}:
    #   include /etc/nginx/snippets/websocket_map.conf;
    # Then change Connection to $connection_upgrade
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_cache_bypass $http_upgrade;
    }
}
