# Phase 3 — Razorpay billing migration
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_plan_alter_subscription_plan'),
    ]

    operations = [
        # Plan: add tier, price_onetime; clean up stripe fields
        migrations.AddField(
            model_name='plan',
            name='tier',
            field=models.CharField(
                choices=[
                    ('trial', 'Trial'), ('basic', 'Basic'),
                    ('pro', 'Pro'), ('enterprise', 'Enterprise'),
                ],
                default='trial',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='plan',
            name='price_onetime',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text='One-time annual payment (0 = not offered)',
            ),
        ),
        migrations.AlterField(
            model_name='plan',
            name='price_monthly',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),

        # Subscription: add status; remove stripe fields
        migrations.AddField(
            model_name='subscription',
            name='status',
            field=models.CharField(
                choices=[
                    ('trial', 'Trial'), ('active', 'Active'),
                    ('expired', 'Expired'), ('cancelled', 'Cancelled'),
                ],
                default='trial',
                max_length=20,
            ),
        ),
        migrations.RemoveField(model_name='subscription', name='stripe_customer_id'),
        migrations.RemoveField(model_name='subscription', name='stripe_subscription_id'),

        # New RazorpayOrder model
        migrations.CreateModel(
            name='RazorpayOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('payment_type', models.CharField(
                    choices=[('onetime', 'One-time'), ('recurring', 'Recurring')],
                    max_length=20,
                )),
                ('razorpay_order_id',   models.CharField(max_length=120, unique=True)),
                ('razorpay_payment_id', models.CharField(blank=True, max_length=120)),
                ('razorpay_signature',  models.CharField(blank=True, max_length=255)),
                ('amount_paise', models.IntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('created', 'Created'), ('paid', 'Paid'), ('failed', 'Failed'),
                    ],
                    default='created',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='razorpay_orders',
                    to='core.organization',
                )),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to='core.plan',
                )),
            ],
        ),
    ]
