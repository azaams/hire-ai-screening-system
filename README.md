# HireAI — AI-Powered CV Screening System

A Django web application that automates the CV screening and candidate ranking process using Google Gemini as the underlying LLM. Recruiters upload candidate CVs in bulk; the system extracts text, evaluates each candidate against a job description, and returns a structured analysis with a match score, strengths, weaknesses, and a hiring recommendation.

---

## Features

- **Bulk CV upload** — process multiple PDF, DOCX, or TXT files in a single submission
- **AI-driven analysis** — match scoring (0–100), pros/cons extraction, and final recommendation via Gemini
- **Demographic inference** — predicted city and gender stored for reporting purposes (not used in scoring)
- **Recruitment dashboard** — ranked candidate table with filterable job positions
- **Visual analytics** — real-time charts for gender distribution, applicant location, and position demand
- **Interview question generator** — on-demand behavioural questions tailored to each candidate's profile
- **Excel export** — one-click `.xlsx` download of the filtered candidate list

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Python 3.11+ |
| AI / LLM | LangChain, Google Gemini (`gemini-2.5-flash`) |
| Database | PostgreSQL |
| Frontend | DaisyUI 4 + Tailwind CSS (CDN), Chart.js |
| Document parsing | PyMuPDF, docx2txt |

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- A Google AI API key ([get one here](https://aistudio.google.com/app/apikey))

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/ai_cv_sorter.git
cd ai_cv_sorter

# 2. Create and activate a virtual environment
python -m venv env
source env/bin/activate        # Linux/macOS
env\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your credentials

# 5. Apply database migrations
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

### Environment Variables

Create a `.env` file in the project root. See `.env.example` for reference:

```ini
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

GOOGLE_API_KEY=your-google-ai-api-key
```

---

## Project Structure

```
ai_cv_sorter/
├── config/              # Django project settings, URLs, WSGI/ASGI
├── cv_sorter/           # Main application
│   ├── migrations/      # Database migrations
│   ├── templates/       # HTML templates
│   ├── admin.py         # Django admin configuration
│   ├── ai_services.py   # LLM integration (document loading, analysis, interview questions)
│   ├── models.py        # Data models: JobDescription, Pelamar, HasilAnalisis
│   ├── urls.py          # App-level URL routing
│   └── views.py         # View logic and API endpoints
├── media/               # Uploaded CV files (git-ignored)
├── .env.example         # Environment variable template
├── .gitignore
├── manage.py
└── requirements.txt
```

---

## License

MIT
