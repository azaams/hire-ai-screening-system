from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_cv, name='upload_cv'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
    path('result/<int:hasil_id>/', views.hasil_detail, name='hasil_detail'),
    path('result/<int:hasil_id>/delete/', views.hapus_hasil, name='hapus_hasil'),
    path('api/chart-data/', views.chart_data, name='chart_data'),
    path('api/saran-interview/<int:hasil_id>/', views.saran_interview_api, name='saran_interview_api'),
    path('export-excel/', views.export_kandidat_excel, name='export_excel'),
]