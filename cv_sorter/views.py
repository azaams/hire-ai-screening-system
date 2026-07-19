import logging
import openpyxl
from collections import defaultdict
from asgiref.sync import async_to_sync

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.core.paginator import Paginator

from .models import JobDescription, Pelamar, HasilAnalisis
from .ai_services import (
    load_single_document,
    analyze_cv_with_llm,
    generate_interview_questions,
)
from .throttle import throttle_ai_endpoint

logger = logging.getLogger(__name__)

DASHBOARD_PAGE_SIZE = 25


@login_required
def dashboard(request):
    """Render the main recruitment dashboard with optional job-position filtering and pagination."""
    job_id = request.GET.get('job_id_filter')
    job_id = int(job_id) if job_id else None

    results = (
        HasilAnalisis.objects
        .select_related('pelamar', 'deskripsi_pekerjaan')
        .order_by('-skor_kecocokan')
    )

    if job_id:
        results = results.filter(deskripsi_pekerjaan_id=job_id)

    for r in results:
        score = r.skor_kecocokan or 0
        r.score = min(max(score, 0), 100)

        if r.score >= 80:
            r.score_class = "text-success"
        elif r.score >= 50:
            r.score_class = "text-warning"
        else:
            r.score_class = "text-error"

    paginator = Paginator(results, DASHBOARD_PAGE_SIZE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'cv_sorter/dashboard.html', {
        'results': page_obj,
        'page_obj': page_obj,
        'all_jobs': JobDescription.objects.all(),
        'selected_job_id': job_id,
    })


@login_required
def upload_cv(request):
    """Handle batch CV upload and trigger AI analysis for each document."""
    job_descriptions = JobDescription.objects.all()

    if request.method == 'POST':
        job_id = request.POST.get('job_description')
        files = request.FILES.getlist('cv_files')

        if not job_id or not files:
            messages.error(request, 'Posisi dan file CV wajib diisi.')
            return redirect('upload_cv')

        job = get_object_or_404(JobDescription, id=job_id)

        success_count = 0
        failure_count = 0

        for cv_file in files:
            try:
                pelamar = Pelamar.objects.create(
                    nama_lengkap=cv_file.name.rsplit('.', 1)[0],
                    cv_file=cv_file,
                )

                cv_text = load_single_document(pelamar.cv_file.path)

                if not cv_text:
                    failure_count += 1
                    continue

                ai_result = async_to_sync(analyze_cv_with_llm)(
                    job_description=job.deskripsi,
                    cv_text=cv_text,
                )

                if not ai_result:
                    failure_count += 1
                    continue

                demographic = ai_result.get('prediksi_data_diri', {})

                HasilAnalisis.objects.create(
                    pelamar=pelamar,
                    deskripsi_pekerjaan=job,
                    skor_kecocokan=ai_result.get('skor_kecocokan', 0),
                    ringkasan_evaluasi=ai_result.get('ringkasan_evaluasi', ''),
                    kelebihan=ai_result.get('kelebihan', []),
                    kekurangan=ai_result.get('kekurangan', []),
                    putusan_akhir=ai_result.get('putusan_akhir', 'Tidak Diketahui'),
                )

                pelamar.kota = demographic.get('kota', 'Tidak Diketahui')
                pelamar.jenis_kelamin = demographic.get('gender', 'Lainnya')
                pelamar.save()

                success_count += 1

            except Exception as e:
                logger.error("Failed to process CV '%s': %s", cv_file.name, e)
                failure_count += 1

        if success_count > 0:
            messages.success(request, f'Berhasil memproses {success_count} dokumen.')
        if failure_count > 0:
            messages.warning(request, f'{failure_count} dokumen gagal diproses atau format tidak terbaca.')

        return redirect('upload_cv')

    grouped_results = defaultdict(list)

    recent_results = (
        HasilAnalisis.objects
        .select_related('pelamar', 'deskripsi_pekerjaan')
        .order_by('-tanggal_analisis')[:10]
    )

    for r in recent_results:
        grouped_results[r.deskripsi_pekerjaan.posisi].append(r)

    return render(request, 'cv_sorter/upload_cv.html', {
        'job_descriptions': job_descriptions,
        'grouped_results': dict(grouped_results),
    })


@login_required
def job_detail(request, job_id):
    """Render the detail page for a specific job opening with its ranked applicant list."""
    job = get_object_or_404(JobDescription, id=job_id)
    analisis_list = (
        HasilAnalisis.objects
        .filter(deskripsi_pekerjaan=job)
        .select_related('pelamar')
        .order_by('-skor_kecocokan')
    )
    return render(request, 'cv_sorter/job_detail.html', {
        'job': job,
        'analisis_list': analisis_list,
    })


@login_required
def hasil_detail(request, hasil_id):
    """Render the detailed analysis page for a single candidate result."""
    hasil = get_object_or_404(HasilAnalisis, id=hasil_id)
    return render(request, 'cv_sorter/hasil_detail.html', {'hasil': hasil})


@login_required
def chart_data(request):
    """Return aggregated demographic and position statistics as JSON for charts."""
    job_id = request.GET.get('job_id_filter')

    queryset = HasilAnalisis.objects.all()
    if job_id:
        queryset = queryset.filter(deskripsi_pekerjaan_id=job_id)

    pelamar_ids = queryset.values_list('pelamar_id', flat=True)
    pelamar_qs = Pelamar.objects.filter(id__in=pelamar_ids)

    gender = pelamar_qs.values('jenis_kelamin').annotate(count=Count('id'))
    kota = pelamar_qs.values('kota').annotate(count=Count('id')).order_by('-count')[:10]

    posisi = []
    if not job_id:
        posisi = (
            HasilAnalisis.objects
            .values('deskripsi_pekerjaan__posisi')
            .annotate(count=Count('id'))
        )

    return JsonResponse({
        'gender': {
            'labels': [g['jenis_kelamin'] for g in gender],
            'data': [g['count'] for g in gender],
        },
        'kota': {
            'labels': [k['kota'] or 'Tidak Diketahui' for k in kota],
            'data': [k['count'] for k in kota],
        },
        'posisi': {
            'labels': [p['deskripsi_pekerjaan__posisi'] for p in posisi],
            'data': [p['count'] for p in posisi],
        },
    })


@login_required
@require_POST
def hapus_hasil(request, hasil_id):
    """Delete a candidate analysis record along with the associated CV file."""
    hasil = get_object_or_404(HasilAnalisis, id=hasil_id)
    pelamar = hasil.pelamar

    if pelamar.cv_file:
        try:
            pelamar.cv_file.delete(save=False)
        except Exception:
            pass

    pelamar.delete()
    return JsonResponse({'success': True, 'message': 'Data pelamar berhasil dihapus.'})


@login_required
@throttle_ai_endpoint(max_calls=5, period=60)
def saran_interview_api(request, hasil_id):
    """Return AI-generated interview questions for a given candidate result (JSON).

    Rate-limited to 5 requests per user per 60 seconds to protect AI API quota.
    """
    hasil = get_object_or_404(HasilAnalisis, id=hasil_id)

    questions = async_to_sync(generate_interview_questions)(
        kelebihan=hasil.kelebihan,
        kekurangan=hasil.kekurangan,
    )

    return JsonResponse({'saran_pertanyaan': questions})


@login_required
def export_kandidat_excel(request):
    """Export filtered candidate results to an Excel (.xlsx) file download."""
    job_id = request.GET.get('job_id_filter')

    results = (
        HasilAnalisis.objects
        .select_related('pelamar', 'deskripsi_pekerjaan')
        .order_by('-skor_kecocokan')
    )

    filename = "Daftar_Semua_Kandidat.xlsx"

    if job_id:
        results = results.filter(deskripsi_pekerjaan_id=job_id)
        try:
            posisi = JobDescription.objects.get(id=job_id).posisi
            safe_posisi = "".join(c for c in posisi if c.isalnum() or c in (' ', '_')).strip()
            filename = f"Kandidat_{safe_posisi.replace(' ', '_')}.xlsx"
        except JobDescription.DoesNotExist:
            pass

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rekap Kandidat"

    headers = [
        'No', 'Nama Kandidat', 'Posisi Dilamar',
        'Skor AI', 'Status Rekomendasi', 'Ringkasan Evaluasi', 'Kota Domisili',
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)

    for idx, r in enumerate(results, start=1):
        ws.append([
            idx,
            r.pelamar.nama_lengkap,
            r.deskripsi_pekerjaan.posisi,
            r.skor_kecocokan,
            r.putusan_akhir,
            r.ringkasan_evaluasi,
            r.pelamar.kota or '-',
        ])

    wb.save(response)
    return response