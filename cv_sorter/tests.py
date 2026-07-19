import io
import json
import tempfile
import os
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from .models import JobDescription, Pelamar, HasilAnalisis
from .ai_services import load_single_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="recruiter", password="testpass123"):
    return User.objects.create_user(username=username, password=password)


def make_job(posisi="Backend Engineer", deskripsi="Django, PostgreSQL required."):
    return JobDescription.objects.create(posisi=posisi, deskripsi=deskripsi)


def make_pelamar(nama="Budi Santoso"):
    return Pelamar.objects.create(
        nama_lengkap=nama,
        cv_file="cvs/dummy.pdf",
        kota="Jakarta",
        jenis_kelamin="Pria",
    )


def make_hasil(pelamar, job, skor=80, putusan="Direkomendasikan"):
    return HasilAnalisis.objects.create(
        pelamar=pelamar,
        deskripsi_pekerjaan=job,
        skor_kecocokan=skor,
        ringkasan_evaluasi="Kandidat memiliki pengalaman relevan.",
        kelebihan=["Django", "PostgreSQL"],
        kekurangan=["Kurang pengalaman di cloud"],
        putusan_akhir=putusan,
    )


# ---------------------------------------------------------------------------
# Unit Tests — ai_services.load_single_document
# ---------------------------------------------------------------------------

class LoadSingleDocumentTest(TestCase):
    """Tests for the document loading and text extraction utility."""

    def test_unsupported_extension_returns_empty_string(self):
        """Files with unsupported extensions (e.g. .xlsx) must return ''."""
        result = load_single_document("/some/path/resume.xlsx")
        self.assertEqual(result, "")

    def test_unknown_extension_returns_empty_string(self):
        """Completely unknown extensions must return ''."""
        result = load_single_document("/some/path/resume.pptx")
        self.assertEqual(result, "")

    @patch("cv_sorter.ai_services.TextLoader")
    def test_short_text_returns_empty_string(self, MockLoader):
        """Documents with fewer than 50 characters of text must return ''."""
        mock_doc = MagicMock()
        mock_doc.page_content = "Too short"
        MockLoader.return_value.load.return_value = [mock_doc]

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Too short")
            tmp_path = f.name

        try:
            result = load_single_document(tmp_path)
            self.assertEqual(result, "")
        finally:
            os.unlink(tmp_path)

    @patch("cv_sorter.ai_services.TextLoader")
    def test_valid_text_file_returns_content(self, MockLoader):
        """A valid text document with sufficient content must return the extracted text."""
        long_text = "A" * 200
        mock_doc = MagicMock()
        mock_doc.page_content = long_text
        MockLoader.return_value.load.return_value = [mock_doc]

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(long_text.encode())
            tmp_path = f.name

        try:
            result = load_single_document(tmp_path)
            self.assertEqual(result, long_text)
        finally:
            os.unlink(tmp_path)

    @patch("cv_sorter.ai_services.PyMuPDFLoader")
    def test_loader_exception_returns_empty_string(self, MockLoader):
        """If the loader raises an exception, the function must return '' gracefully."""
        MockLoader.return_value.load.side_effect = Exception("Corrupted file")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name

        try:
            result = load_single_document(tmp_path)
            self.assertEqual(result, "")
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Integration Tests — Views
# ---------------------------------------------------------------------------

class AuthRedirectTest(TestCase):
    """Unauthenticated requests must redirect to the login page."""

    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('dashboard')}")

    def test_upload_cv_requires_login(self):
        response = self.client.get(reverse("upload_cv"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('upload_cv')}")

    def test_export_excel_requires_login(self):
        response = self.client.get(reverse("export_excel"))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('export_excel')}")


class DashboardViewTest(TestCase):
    """Tests for the main recruitment dashboard."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)
        self.job = make_job()
        self.pelamar = make_pelamar()
        self.hasil = make_hasil(self.pelamar, self.job)

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_correct_template(self):
        response = self.client.get(reverse("dashboard"))
        self.assertTemplateUsed(response, "cv_sorter/dashboard.html")

    def test_dashboard_contains_candidate(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, self.pelamar.nama_lengkap)

    def test_dashboard_filter_by_job(self):
        response = self.client.get(reverse("dashboard"), {"job_id_filter": self.job.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_job_id"], self.job.id)


class UploadCvViewTest(TestCase):
    """Tests for the CV upload form view."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_upload_page_returns_200(self):
        response = self.client.get(reverse("upload_cv"))
        self.assertEqual(response.status_code, 200)

    def test_post_without_job_id_redirects_with_error(self):
        response = self.client.post(reverse("upload_cv"), {"cv_files": []})
        self.assertRedirects(response, reverse("upload_cv"))

    def test_post_without_files_redirects_with_error(self):
        job = make_job()
        response = self.client.post(
            reverse("upload_cv"), {"job_description": job.id, "cv_files": []}
        )
        self.assertRedirects(response, reverse("upload_cv"))


class HapusHasilViewTest(TestCase):
    """Tests for the candidate deletion endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)
        self.job = make_job()
        self.pelamar = make_pelamar()
        self.hasil = make_hasil(self.pelamar, self.job)

    def test_delete_via_get_returns_405(self):
        """Deletion endpoint must only accept POST requests."""
        response = self.client.get(
            reverse("hapus_hasil", kwargs={"hasil_id": self.hasil.id})
        )
        self.assertEqual(response.status_code, 405)

    def test_delete_via_post_returns_success_json(self):
        response = self.client.post(
            reverse("hapus_hasil", kwargs={"hasil_id": self.hasil.id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])

    def test_delete_removes_record_from_db(self):
        hasil_id = self.hasil.id
        self.client.post(
            reverse("hapus_hasil", kwargs={"hasil_id": hasil_id}),
            content_type="application/json",
        )
        self.assertFalse(HasilAnalisis.objects.filter(id=hasil_id).exists())


class ChartDataViewTest(TestCase):
    """Tests for the chart data API endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_chart_data_returns_200(self):
        response = self.client.get(reverse("chart_data"))
        self.assertEqual(response.status_code, 200)

    def test_chart_data_has_required_keys(self):
        response = self.client.get(reverse("chart_data"))
        data = json.loads(response.content)
        self.assertIn("gender", data)
        self.assertIn("kota", data)
        self.assertIn("posisi", data)

    def test_chart_data_structure(self):
        """Each key must contain 'labels' and 'data' sub-keys."""
        response = self.client.get(reverse("chart_data"))
        data = json.loads(response.content)
        for key in ("gender", "kota", "posisi"):
            self.assertIn("labels", data[key])
            self.assertIn("data", data[key])


class ExportExcelViewTest(TestCase):
    """Tests for the Excel export endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)
        job = make_job()
        pelamar = make_pelamar()
        make_hasil(pelamar, job)

    def test_export_returns_xlsx_content_type(self):
        response = self.client.get(reverse("export_excel"))
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_export_has_content_disposition_header(self):
        response = self.client.get(reverse("export_excel"))
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".xlsx", response["Content-Disposition"])


class JobDetailViewTest(TestCase):
    """Tests for the job detail page."""

    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.client.force_login(self.user)
        self.job = make_job()
        self.pelamar = make_pelamar()
        self.hasil = make_hasil(self.pelamar, self.job)

    def test_job_detail_returns_200(self):
        response = self.client.get(
            reverse("job_detail", kwargs={"job_id": self.job.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_job_detail_shows_job_position(self):
        response = self.client.get(
            reverse("job_detail", kwargs={"job_id": self.job.id})
        )
        self.assertContains(response, self.job.posisi)

    def test_job_detail_shows_applicant(self):
        response = self.client.get(
            reverse("job_detail", kwargs={"job_id": self.job.id})
        )
        self.assertContains(response, self.pelamar.nama_lengkap)

    def test_job_detail_invalid_id_returns_404(self):
        response = self.client.get(
            reverse("job_detail", kwargs={"job_id": 99999})
        )
        self.assertEqual(response.status_code, 404)
