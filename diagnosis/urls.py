"""
URL configuration for diagnosis app
"""
from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    
    # Authentication
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard (authenticated)
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Patient management (authenticated)
    path('patient/new/', views.patient_input, name='patient_input'),
    path('patient/<str:patient_id>/edit/', views.patient_edit, name='patient_edit'),
    path('patient/<str:patient_id>/delete/', views.patient_delete, name='patient_delete'),
    path('patient/<str:patient_id>/follow-up/', views.patient_follow_up, name='patient_follow_up'),
    path('patient/<str:patient_id>/', views.patient_detail, name='patient_detail'),
    path('patient/<str:patient_id>/visit/<int:visit_number>/edit/', views.visit_edit, name='visit_edit'),
    path('patient/<str:patient_id>/visit/<int:visit_number>/diagnose/', views.generate_diagnosis, name='generate_diagnosis'),
    path('patient/<str:patient_id>/visit/<int:visit_number>/regenerate/', views.regenerate_diagnosis, name='regenerate_diagnosis'),
    path('diagnosis/<int:diagnosis_id>/', views.diagnosis_result, name='diagnosis_result'),
    path('diagnosis-job/<uuid:job_id>/', views.diagnosis_job_detail, name='diagnosis_job_detail'),
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/archived/', views.patient_archived_list, name='patient_archived_list'),
    path('patient/<str:patient_id>/restore/', views.patient_restore, name='patient_restore'),
]
