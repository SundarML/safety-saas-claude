from django.contrib import admin
from .models import HazardRegister, Hazard

class HazardInline(admin.TabularInline):
    model = Hazard
    extra = 0
    fields = ['category', 'hazard_description', 'initial_likelihood', 'initial_severity',
              'residual_likelihood', 'residual_severity']

@admin.register(HazardRegister)
class HazardRegisterAdmin(admin.ModelAdmin):
    list_display  = ['title', 'organization', 'status', 'assessment_date', 'next_review_date', 'assessed_by']
    list_filter   = ['status', 'organization']
    search_fields = ['title', 'activity']
    inlines       = [HazardInline]

@admin.register(Hazard)
class HazardAdmin(admin.ModelAdmin):
    list_display  = ['register', 'category', 'hazard_description', 'initial_risk_score_display', 'residual_risk_score_display']
    list_filter   = ['category', 'register__organization']

    def initial_risk_score_display(self, obj):
        return obj.initial_risk_score
    initial_risk_score_display.short_description = "Initial Score"

    def residual_risk_score_display(self, obj):
        return obj.residual_risk_score or "—"
    residual_risk_score_display.short_description = "Residual Score"
