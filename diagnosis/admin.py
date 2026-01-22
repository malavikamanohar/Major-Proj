from django.contrib import admin
from .models import Patient, Vitals, Labs, ClinicalSummary, KnowledgeCase, DiagnosisResult, LLMUsage, UserProfile


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
    list_display = ['patient_id', 'age', 'sex', 'chief_complaint', 'created_at']
    search_fields = ['patient_id', 'chief_complaint']
    list_filter = ['sex', 'created_at']


@admin.register(Vitals)
class VitalsAdmin(admin.ModelAdmin):
    list_display = ['patient', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'heart_rate', 'recorded_at']


@admin.register(Labs)
class LabsAdmin(admin.ModelAdmin):
    list_display = ['patient', 'recorded_at']


@admin.register(ClinicalSummary)
class ClinicalSummaryAdmin(admin.ModelAdmin):
    list_display = ['patient', 'created_at']


@admin.register(KnowledgeCase)
class KnowledgeCaseAdmin(admin.ModelAdmin):
    list_display = ['case_id', 'diagnosis', 'created_at']
    search_fields = ['case_id', 'diagnosis', 'summary_text']


@admin.register(DiagnosisResult)
class DiagnosisResultAdmin(admin.ModelAdmin):
    list_display = ['patient', 'triage_level', 'confidence_score', 'created_at']
    list_filter = ['triage_level', 'created_at']

