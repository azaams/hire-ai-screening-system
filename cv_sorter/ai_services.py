import os
import logging
from typing import List, Optional, Dict

from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyMuPDFLoader, Docx2txtLoader, TextLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger(__name__)


class CandidateEvaluation(BaseModel):
    skor_kecocokan: int = Field(
        ...,
        description="Skor kecocokan kandidat dari 0 hingga 100 berdasarkan kualifikasi teknis dan pengalaman.",
    )
    ringkasan_evaluasi: str = Field(
        ...,
        description="Ringkasan evaluasi singkat dan padat (2-3 kalimat) mengenai profil kandidat.",
    )
    kelebihan: List[str] = Field(
        ...,
        description="Daftar poin-poin kekuatan utama (hard skill/soft skill) yang relevan dengan posisi.",
    )
    kekurangan: List[str] = Field(
        ...,
        description="Daftar poin-poin kekurangan, gap skill, atau area yang perlu diklarifikasi saat interview.",
    )
    putusan_akhir: str = Field(
        ...,
        description="Rekomendasi akhir: 'Sangat Direkomendasikan', 'Direkomendasikan', 'Dipertimbangkan', atau 'Tidak Direkomendasikan'.",
    )
    prediksi_data_diri: Dict[str, str] = Field(
        ...,
        description="Dictionary berisi prediksi {'kota': 'Nama Kota/Tidak Diketahui', 'gender': 'Pria/Wanita/Lainnya'}.",
    )


class InterviewSuggestions(BaseModel):
    saran_pertanyaan: List[str] = Field(
        ...,
        description="Daftar 3-5 pertanyaan interview mendalam (Behavioral/Technical) berdasarkan analisis CV.",
    )


def load_single_document(file_path: str) -> str:
    """
    Load and extract plain text from a CV document.

    Supports PDF, DOCX, and TXT formats. Returns an empty string if the
    file format is unsupported, the file cannot be read, or the extracted
    text is too short to be meaningful (< 50 characters).
    """
    ext = os.path.splitext(file_path)[1].lower()

    loaders = {
        ".pdf": lambda: PyMuPDFLoader(file_path),
        ".docx": lambda: Docx2txtLoader(file_path),
        ".txt": lambda: TextLoader(file_path, encoding="utf-8"),
    }

    loader_factory = loaders.get(ext)
    if not loader_factory:
        logger.warning("Unsupported file format, skipping: %s", file_path)
        return ""

    try:
        docs = loader_factory().load()
        full_text = "\n".join(d.page_content for d in docs)

        if len(full_text.strip()) < 50:
            logger.warning(
                "Extracted text too short in '%s' — file may be image-based or scanned.",
                os.path.basename(file_path),
            )
            return ""

        return full_text

    except Exception as e:
        logger.error("Failed to load document '%s': %s", os.path.basename(file_path), e)
        return ""


async def analyze_cv_with_llm(job_description: str, cv_text: str) -> Optional[dict]:
    """
    Analyse a CV against a job description using the Gemini LLM.

    Sends both documents to the model with a structured prompt and returns
    a parsed dictionary matching the CandidateEvaluation schema.
    Returns None if either input is empty or if the LLM call fails.
    """
    if not cv_text or not job_description:
        logger.warning("Empty input received — both CV text and job description are required.")
        return None

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.3,
        max_retries=2,
    )

    parser = JsonOutputParser(pydantic_object=CandidateEvaluation)

    prompt_template = """
    Anda adalah Senior Technical Recruiter AI yang sangat teliti, objektif, dan profesional.
    Tugas Anda adalah membandingkan profil kandidat (CV) dengan kebutuhan pekerjaan (JD).

    INSTRUKSI PENILAIAN:
    1. **Identifikasi Kualifikasi Wajib:** Baca JD dan temukan skill/pengalaman kunci yang diminta.
    2. **Verifikasi Bukti:** Cari bukti pengalaman tersebut di dalam CV. Jangan berasumsi jika tidak tertulis.
    3. **Anti-Bias:** Abaikan nama, ras, agama, atau gender dalam penentuan skor dan kelayakan.
    4. **Skoring:** Berikan skor 0-100 secara ketat berdasarkan seberapa banyak kualifikasi wajib terpenuhi.
    5. **Prediksi Data:** Coba prediksi domisili dan gender dari konteks nama/alamat (hanya untuk data entry, bukan penilaian).

    KELUARAN (OUTPUT):
    Jawab HANYA dalam format JSON sesuai skema berikut.

    {format_instructions}

    === DESKRIPSI PEKERJAAN (JD) ===
    {job_description}

    === KONTEKS CV KANDIDAT ===
    {cv_context}
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["job_description", "cv_context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        logger.info("Sending CV analysis request to Gemini...")
        result = await chain.ainvoke({
            "job_description": job_description,
            "cv_context": cv_text,
        })
        return result
    except Exception as e:
        logger.error("LLM analysis failed: %s", e)
        return None


async def generate_interview_questions(kelebihan: List[str], kekurangan: List[str]) -> List[str]:
    """
    Generate tailored interview questions based on a candidate's strengths and weaknesses.

    Returns a list of 3–5 behavioural or situational questions. Returns an
    empty list if the LLM call fails.
    """
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.6,
    )

    parser = JsonOutputParser(pydantic_object=InterviewSuggestions)

    prompt_template = """
    Anda adalah Hiring Manager. Berdasarkan poin kelebihan dan kekurangan kandidat di bawah ini,
    buatlah daftar pertanyaan interview untuk memvalidasi kandidat tersebut.

    INSTRUKSI:
    1. Buat 3-5 pertanyaan.
    2. Pertanyaan harus bersifat *Behavioral* atau *Situational* (misal: "Ceritakan masa ketika...").
    3. Fokus: Validasi kelebihan dan klarifikasi kekurangan secara sopan namun tajam.

    {format_instructions}

    === KELEBIHAN ===
    {kelebihan}

    === KEKURANGAN/AREA PERBAIKAN ===
    {kekurangan}
    """

    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["kelebihan", "kekurangan"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    chain = prompt | llm | parser

    try:
        result = await chain.ainvoke({
            "kelebihan": "\n".join(kelebihan),
            "kekurangan": "\n".join(kekurangan),
        })
        return result.get("saran_pertanyaan", [])
    except Exception as e:
        logger.error("Failed to generate interview questions: %s", e)
        return []