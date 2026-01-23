from django.contrib import admin
from .models import Patient, Visit, Vitals, Labs, ClinicalSummary, KnowledgeCase, DiagnosisResult, DiagnosisJob, LLMUsage, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'license_number', 'created_at']
    list_filter = ['role', 'department']
    search_fields = ['user__username', 'user__email', 'license_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ['model_name', 'api_key_fingerprint', 'date', 'count', 'updated_at']
    list_filter = ['model_name', 'date']
    search_fields = ['model_name', 'api_key_fingerprint']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['patient_id', 'last_name', 'first_name', 'age', 'sex', 'phone_number', 'created_at']
    search_fields = ['patient_id', 'first_name', 'last_name', 'phone_number', 'email']
    list_filter = ['sex', 'created_at']
    fieldsets = (
        ('Identification', {
            'fields': ('patient_id', 'first_name', 'last_name', 'date_of_birth', 'age', 'sex')
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'email', 'address')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Medical History', {
            'fields': ('past_medical_history', 'medications')
        }),
    )


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['patient', 'visit_number', 'visit_type', 'chief_complaint', 'created_at']
    search_fields = ['patient__patient_id', 'chief_complaint']
    list_filter = ['visit_type', 'created_at']


@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
    list_display = ['visit', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate', 'recorded_at']


@admin.register(Labs)
class LabsAdmin(admin.ModelAdmin):
    list_display = ['visit', 'recorded_at']


@admin.register(ClinicalSummary)
class ClinicalSummaryAdmin(admin.ModelAdmin):
    list_display = ['visit', 'created_at']


@admin.register(KnowledgeCase)
class KnowledgeCaseAdmin(admin.ModelAdmin):
    list_display = ['case_id', 'diagnosis', 'created_at']
    search_fields = ['case_id', 'diagnosis', 'summary_text']


@admin.register(DiagnosisResult)
class DiagnosisResultAdmin(admin.ModelAdmin):
    list_display = ['visit', 'triage_level', 'confidence_score', 'created_at']
    list_filter = ['triage_level', 'created_at']


@admin.register(DiagnosisJob)
class DiagnosisJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'visit', 'status', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'visit__patient__patient_id']

