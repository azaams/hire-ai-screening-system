import os

from django.db import models


class JobDescription(models.Model):
    posisi = models.CharField(max_length=255, help_text="Contoh: Frontend Developer")
    deskripsi = models.TextField(help_text="Salin-tempel deskripsi pekerjaan di sini")
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.posisi


class Pelamar(models.Model):
    class GenderChoices(models.TextChoices):
        PRIA = 'Pria', 'Pria'
        WANITA = 'Wanita', 'Wanita'
        LAINNYA = 'Lainnya', 'Lainnya'
        TIDAK_DIKETAHUI = 'Tidak Diketahui', 'Tidak Diketahui'

    nama_lengkap = models.CharField(max_length=255)
    cv_file = models.FileField(upload_to='cvs/')
    tanggal_upload = models.DateTimeField(auto_now_add=True)
    kota = models.CharField(max_length=100, blank=True, null=True)
    jenis_kelamin = models.CharField(
        max_length=20,
        choices=GenderChoices.choices,
        default=GenderChoices.TIDAK_DIKETAHUI,
    )

    def __str__(self):
        return self.nama_lengkap

    def get_filename(self):
        return os.path.basename(self.cv_file.name)


class HasilAnalisis(models.Model):
    pelamar = models.ForeignKey(Pelamar, on_delete=models.CASCADE)
    deskripsi_pekerjaan = models.ForeignKey(JobDescription, on_delete=models.CASCADE)
    skor_kecocokan = models.IntegerField()
    ringkasan_evaluasi = models.TextField()
    kelebihan = models.JSONField(default=list)
    kekurangan = models.JSONField(default=list)
    putusan_akhir = models.CharField(max_length=100)
    tanggal_analisis = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-skor_kecocokan']

    def __str__(self):
        return f"Hasil untuk {self.pelamar.nama_lengkap} pada posisi {self.deskripsi_pekerjaan.posisi}"