# Generated migration for normalizing plan codes
# MONTHLY -> PRO_MONTHLY, YEARLY -> PRO_YEARLY

from django.db import migrations


def normalize_plan_codes(apps, schema_editor):
    """
    Normalize legacy plan codes to new format.
    
    MONTHLY -> PRO_MONTHLY
    YEARLY -> PRO_YEARLY
    
    This ensures consistency across frontend and backend.
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')
    
    # Map old codes to new
    code_mapping = {
        'MONTHLY': 'PRO_MONTHLY',
        'YEARLY': 'PRO_YEARLY',
    }
    
    for old_code, new_code in code_mapping.items():
        # Check if old code exists and new code doesn't
        old_plan = SubscriptionPlan.objects.filter(code=old_code).first()
        new_plan = SubscriptionPlan.objects.filter(code=new_code).first()
        
        if old_plan and not new_plan:
            # Update the code
            old_plan.code = new_code
            old_plan.save()
            print(f"Migrated plan code: {old_code} -> {new_code}")
        elif old_plan and new_plan:
            print(f"Both {old_code} and {new_code} exist. Manual cleanup needed.")
        else:
            print(f"Plan with code {old_code} not found. Skipping.")


def reverse_normalize_plan_codes(apps, schema_editor):
    """
    Reverse migration: PRO_MONTHLY -> MONTHLY, PRO_YEARLY -> YEARLY
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')
    
    # Map new codes back to old
    code_mapping = {
        'PRO_MONTHLY': 'MONTHLY',
        'PRO_YEARLY': 'YEARLY',
    }
    
    for new_code, old_code in code_mapping.items():
        plan = SubscriptionPlan.objects.filter(code=new_code).first()
        if plan:
            plan.code = old_code
            plan.save()
            print(f"Reversed plan code: {new_code} -> {old_code}")


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0011_payment_webhook_processed_at_webhooklog'),
    ]

    operations = [
        migrations.RunPython(
            normalize_plan_codes,
            reverse_code=reverse_normalize_plan_codes
        ),
    ]
