# Жизненный цикл подписки

## Обзор

Каждый пользователь имеет ровно **одну подписку** (1:1 с User).

При регистрации автоматически создаётся FREE подписка.

---

## Состояния

```
[Регистрация] → FREE (активно)
           ↓
[Оплата PRO] → PRO_MONTHLY/PRO_YEARLY (активно)
           ↓
[Истечение] → PRO (неактивно) → [cleanup] → FREE
           или
[Автопродление] → PRO (продлено)
```

---

## Тарифные планы

| Code | Название | Цена | Длительность | Лимит фото |
|------|----------|------|--------------|------------|
| `FREE` | Бесплатный | 0 ₽ | ∞ | 3/день |
| `PRO_MONTHLY` | PRO месячный | 299 ₽ | 30 дней | ∞ |
| `PRO_YEARLY` | PRO годовой | 1990 ₽ | 365 дней | ∞ |

---

## Модель Subscription

| Поле | Описание |
|------|----------|
| `user` | OneToOne с User |
| `plan` | FK на SubscriptionPlan |
| `start_date` | Начало подписки |
| `end_date` | Окончание подписки |
| `is_active` | Активна ли |
| `auto_renew` | Автопродление |
| `yookassa_payment_method_id` | Сохранённая карта |
| `card_mask` | •••• 1234 |
| `card_brand` | Visa/MasterCard/МИР |

---

## Методы модели

### is_expired()

```python
def is_expired(self) -> bool:
    """FREE никогда не истекает."""
    if self.plan.code == "FREE":
        return False
    return timezone.now() >= self.end_date
```

### days_remaining (property)

```python
@property
def days_remaining(self):
    """FREE → None, expired → 0."""
    if self.plan.code == "FREE":
        return None
    if not self.is_active or self.is_expired():
        return 0
    return max(0, (self.end_date - timezone.now()).days)
```

---

## Активация подписки

При успешном webhook вызывается:

```python
activate_or_extend_subscription(
    user=payment.user,
    plan_code=plan.code,
    duration_days=plan.duration_days,
)
```

**Логика:**
- Если подписка истекла → новый период от `now()`
- Если активна → добавляем дни к `end_date`

---

## Автопродление

### Условия

1. `auto_renew=True`
2. `yookassa_payment_method_id` сохранён
3. `BILLING_RECURRING_ENABLED=true`

### Процесс

1. Command `process_recurring_payments` запускается по cron
2. Находит подписки истекающие в ближайшие N дней
3. Создаёт рекуррентный платёж через `YooKassaService`
4. Webhook обрабатывается как обычный платёж

---

## Сигналы

### create_free_subscription

При создании User автоматически создаётся FREE подписка:

```python
@receiver(post_save, sender=User)
def create_free_subscription(sender, instance, created, **kwargs):
    if created:
        Subscription.objects.create(
            user=instance,
            plan=free_plan,
            start_date=now(),
            end_date=now() + timedelta(days=365*10),
            is_active=True,
        )
```

---

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `GET /billing/me/` | Короткий статус (план, лимиты) |
| `GET /billing/subscription/` | Полная карточка |
| `POST /billing/subscription/autorenew/` | Вкл/выкл автопродление |
