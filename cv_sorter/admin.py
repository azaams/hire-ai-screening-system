from django.contrib import admin

from .models import JobDescription, Pelamar, HasilAnalisis


class HasilAnalisisAdmin(admin.ModelAdmin):
    list_display = ('pelamar', 'deskripsi_pekerjaan', 'skor_kecocokan', 'putusan_akhir', 'tanggal_analisis')
    list_filter = ('deskripsi_pekerjaan', 'putusan_akhir')
    search_fields = ('pelamar__nama_lengkap',)


admin.site.register(JobDescription)
admin.site.register(Pelamar)
admin.site.register(HasilAnalisis, HasilAnalisisAdmin)