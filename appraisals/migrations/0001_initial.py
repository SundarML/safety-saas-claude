from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppraisalCycle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('period', models.CharField(choices=[('annual', 'Annual'), ('semi_annual', 'Semi-Annual'), ('quarterly', 'Quarterly'), ('custom', 'Custom')], default='annual', max_length=20)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('goal_setting_deadline', models.DateField()),
                ('self_assessment_deadline', models.DateField()),
                ('review_deadline', models.DateField()),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('goal_setting', 'Goal Setting'), ('self_assessment', 'Self Assessment'), ('manager_review', 'Manager Review'), ('calibration', 'Calibration'), ('completed', 'Completed')], default='draft', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appraisal_cycles', to='core.organization')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appraisal_cycles_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='AppraisalCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('category_type', models.CharField(choices=[('goals', 'Goals & Targets'), ('competency', 'Competency'), ('custom', 'Custom Rating')], default='goals', max_length=20)),
                ('weight', models.DecimalField(decimal_places=2, max_digits=5)),
                ('order', models.PositiveIntegerField(default=0)),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categories', to='appraisals.appraisalcycle')),
            ],
            options={'ordering': ['order', 'id']},
        ),
        migrations.CreateModel(
            name='AppraisalRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending_goals', 'Pending Goals'), ('goals_set', 'Goals Set'), ('self_assessment', 'Self Assessment'), ('pending_review', 'Pending Review'), ('acknowledged', 'Acknowledged')], default='pending_goals', max_length=25)),
                ('overall_score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('overall_rating', models.CharField(blank=True, choices=[('exceptional', 'Exceptional'), ('exceeds', 'Exceeds Expectations'), ('meets', 'Meets Expectations'), ('needs_improvement', 'Needs Improvement'), ('unsatisfactory', 'Unsatisfactory')], max_length=25)),
                ('manager_summary', models.TextField(blank=True)),
                ('development_plan', models.TextField(blank=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='records', to='appraisals.appraisalcycle')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appraisal_records', to=settings.AUTH_USER_MODEL)),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appraisal_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['employee__full_name'], 'unique_together': {('cycle', 'employee')}},
        ),
        migrations.CreateModel(
            name='AppraisalItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('item_type', models.CharField(choices=[('measurable', 'Measurable (has target value)'), ('rating', 'Rating (1–5 scale)'), ('yes_no', 'Yes / No')], default='rating', max_length=15)),
                ('weight', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5)),
                ('target_value', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('target_unit', models.CharField(blank=True, max_length=50)),
                ('goal_type', models.CharField(choices=[('manager_set', 'Manager Assigned'), ('self_set', 'Employee Proposed')], default='manager_set', max_length=15)),
                ('approved_by_manager', models.BooleanField(default=False)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appraisal_items_approved', to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='appraisals.appraisalcategory')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appraisal_items_created', to=settings.AUTH_USER_MODEL)),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='appraisals.appraisalrecord')),
            ],
            options={'ordering': ['category__order', 'created_at']},
        ),
        migrations.CreateModel(
            name='AppraisalRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('actual_value', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('self_rating', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('self_comment', models.TextField(blank=True)),
                ('manager_rating', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('manager_comment', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='appraisals.appraisalitem')),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ratings', to='appraisals.appraisalrecord')),
            ],
            options={'unique_together': {('record', 'item')}},
        ),
    ]
