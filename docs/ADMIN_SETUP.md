# Django Admin Setup Documentation

**Date:** 2025-12-26
**Status:** ✅ Configured and Ready

---

## Django Admin Access

### Credentials

- **Admin Panel URL:** https://eatfit24.ru/dj-admin/
- **Username:** `nick`
- **Password:** `Ghfverfghfvert123`
- **Email:** admin@eatfit24.ru

### Permissions

- Superuser: ✅ Yes
- Staff status: ✅ Yes
- Active: ✅ Yes

---

## Configuration Applied (2025-12-26)

### 1. OpenRouter API Key Configured

```bash
OPENROUTER_API_KEY=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
```

**Status:** ✅ AI features now enabled

### 2. Django Superuser Created

```bash
docker compose exec backend python manage.py createsuperuser
```

**Created user:**
- Username: nick
- Email: admin@eatfit24.ru
- Superuser status: Yes

**Verification:**
```bash
docker compose exec -T backend python manage.py shell -c \
  "from django.contrib.auth import get_user_model; \
   User = get_user_model(); \
   print('Superusers:', User.objects.filter(is_superuser=True).count())"
```

Output: `Superusers: 1`

### 3. Security Fix Script Deployed

**Script:** `scripts/fix-critical-security.sh`

**Permissions:** `-rwxr-xr-x` (executable)

**Location:** `/opt/EatFit24/scripts/fix-critical-security.sh`

**Status:** Ready to execute (not yet run)

---

## Admin Panel Features

The Django admin panel provides access to:

### User Management
- Users (apps.users.User)
- Groups and Permissions
- User activity logs

### Nutrition Management
- Nutrition Plans
- Meals and Foods
- Dietary Preferences

### Billing Management
- Subscriptions
- Payments
- YooKassa webhooks

### AI Services
- AI Requests log
- Model usage statistics

### Telegram Integration
- Telegram Users
- Bot interactions log

---

## Security Notes

### ✅ Good Practices Applied

1. **Admin URL obfuscated:** Using `/dj-admin/` instead of default `/admin/`
2. **Strong password:** 18 characters with mixed case and numbers
3. **Credentials documented:** Safely stored in `.env` file (not in git)
4. **HTTPS enforced:** All admin access over SSL

### ⚠️ Remaining Security Tasks

From [SECURITY_AUDIT.md](SECURITY_AUDIT.md):

1. **Critical (not yet applied):**
   - Run `./scripts/fix-critical-security.sh` to fix SECRET_KEY and SWAGGER_AUTH_PASSWORD
   - Restart Docker services after .env changes

2. **High Priority:**
   - Configure production YooKassa credentials (currently in test mode)
   - Remove duplicate environment variables (SECRET_KEY vs DJANGO_SECRET_KEY)

3. **Medium Priority:**
   - Set up Telegram bot token rotation schedule
   - Consider secrets manager for sensitive credentials

---

## Verification Checklist

- [x] Admin URL accessible (HTTP 403 at login page = correct)
- [x] Superuser created (nick)
- [x] Credentials documented in .env
- [x] OpenRouter API key configured
- [x] Security fix script deployed and executable
- [ ] SECRET_KEY fixed (pending script execution)
- [ ] SWAGGER_AUTH_PASSWORD fixed (pending script execution)
- [ ] Docker services restarted after .env changes

---

## Quick Commands

### Login to Admin Panel

1. Open browser: https://eatfit24.ru/dj-admin/
2. Enter credentials:
   - Username: `nick`
   - Password: `Ghfverfghfvert123`

### Check Superusers via SSH

```bash
ssh deploy@eatfit24.ru
cd /opt/EatFit24
docker compose exec backend python manage.py shell -c \
  "from django.contrib.auth import get_user_model; \
   User = get_user_model(); \
   for u in User.objects.filter(is_superuser=True): \
       print(f'{u.username} - {u.email} - Active: {u.is_active}')"
```

### Create Additional Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

### Reset Admin Password

```bash
docker compose exec backend python manage.py changepassword nick
```

---

## Troubleshooting

### Cannot Login to Admin

**Problem:** Login fails with credentials

**Check:**
1. Verify user exists and is active:
   ```bash
   docker compose exec backend python manage.py shell -c \
     "from django.contrib.auth import get_user_model; \
      User = get_user_model(); \
      u = User.objects.get(username='nick'); \
      print(f'Active: {u.is_active}, Staff: {u.is_staff}, Superuser: {u.is_superuser}')"
   ```

2. Reset password if needed:
   ```bash
   docker compose exec backend python manage.py changepassword nick
   ```

### Admin URL Returns 404

**Problem:** https://eatfit24.ru/admin/ returns 404

**Solution:** Use correct URL: https://eatfit24.ru/dj-admin/

### CSRF Verification Failed

**Problem:** Login shows CSRF error

**Check:**
1. ALLOWED_HOSTS includes domain:
   ```bash
   grep ALLOWED_HOSTS .env
   ```

2. Nginx X-Forwarded-For headers configured:
   ```bash
   curl -I https://eatfit24.ru/dj-admin/
   ```

---

## Related Documentation

- [SECURITY_AUDIT.md](SECURITY_AUDIT.md) - Comprehensive security audit
- [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md) - Production deployment details
- [HEALTH_CHECK_REPORT.md](HEALTH_CHECK_REPORT.md) - Server stability monitoring

---

**Last Updated:** 2025-12-26
**Configured By:** DevOps Agent
