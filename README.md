# ⚡ ApexLead • Autonomous B2B Lead Enrichment Agent

An autonomous, multi-step B2B lead enrichment pipeline that accepts company domains, crawls their web presence with Playwright headless browser automation, optimizes token consumption via semantic HTML pre-processing, extracts structured intelligence via strict Pydantic schemas using Google Gemini / OpenAI / Groq, enriches missing leadership LinkedIn profiles & contacts via search fallback, and visualizes results in a sleek Streamlit web dashboard and CLI.

Benchmarked and tested against:
- **`postman.com`**
- **`supabase.com`**
- **`vapi.ai`**

---

## 🌟 Architecture & Capabilities

```
 Target Domain(s)
       │
       ▼
 [ 1. Playwright Headless Crawler ] ───► Dynamic JS Rendering & Balanced Subpage Discovery
       │                                  (/about, /team, /company, /contact, /pricing)
       ▼
 [ 2. Semantic Pre-Processor ]     ───► Strips scripts, SVGs, styles, modals
       │                                  85%–95% token compression to Markdown
       │                                  Pre-extracts emails, phones & contact URLs
       ▼
 [ 3. Structured LLM Engine ]      ───► Strict Pydantic Schema Validation
       │                                  (Company Overview, ICP, Contacts, Leadership)
       ▼
 [ 4. External Search Fallback ]   ───► DDGS Search Fallback for missing LinkedIn & contacts
       │
       ▼
 [ 5. Output Presentation ]        ───► Streamlit Gradual Dark Dashboard & Rich CLI
                                          Summary Table, Token Cost Metrics, JSON & CSV Export
```

### Core Features
- **Headless Chromium Automation**: Playwright renders client-side dynamic JavaScript (React, Vue, Next.js). Automatically falls back to HTTPX if needed.
- **Balanced Subpage Discovery**: Proactively fetches both **Leadership/About** pages and **Contact/Sales** pages, ensuring balanced B2B intelligence.
- **Context & Token Optimization**: Strips HTML noise, achieving ~85%–95% token footprint reduction.
- **Strict Pydantic Validation**: Guarantees consistent schema adherence (`ExtractedLeadIntelligence`, `LeadershipMember`, `TokenUsage`).
- **Multi-Channel Contact Discovery**: Captures verified email addresses, phone numbers, and official contact/sales form URLs from pages and search fallback.
- **Executive LinkedIn Enrichment**: Automatically discovers missing executive and founder LinkedIn profile URLs via DuckDuckGo search fallback.
- **Real-Time Cost Tracking**: Calculates prompt, completion, and total tokens used alongside live USD expenditure tracking.
- **Gradual Dark Theme UI**: Streamlit application with gradual light-to-dark gradient, unified multi-domain input, live terminal stream, summary table, and one-click JSON/CSV downloads.

---

## 📁 Project Structure

```
Lead-Enrichment Agent/
├── core/
│   ├── __init__.py           # Package exports
│   ├── models.py             # Strict Pydantic data schemas
│   ├── crawler.py            # Playwright headless crawler & subpage discovery
│   ├── preprocessor.py       # HTML sanitization & semantic Markdown converter
│   ├── llm.py                # Multi-provider structured LLM engine (Gemini 3.6, etc.)
│   ├── search.py             # DuckDuckGo search engine fallback
│   └── agent.py              # Central multi-step agent orchestrator
├── tests/
│   ├── __init__.py
│   ├── test_crawler_models.py # Unit tests for models & crawler
│   └── test_preprocessor.py   # Unit tests for HTML cleaning & contact extraction
├── output/
│   └── results.json          # Benchmark execution output
├── app.py                    # Streamlit interactive web dashboard
├── main.py                   # Command-line interface with Rich tables
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Project packaging specification
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore rules for secrets and build files
└── README.md                 # Project documentation
```

---

## 🚀 Local Setup & Installation

### Prerequisites
- **Python 3.10+** installed on your system.
- An LLM API key (e.g. **Google Gemini API Key** — recommended, or OpenAI / Groq).

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/lead-enrichment-agent.git
cd lead-enrichment-agent
```

### 2. Create and Activate a Virtual Environment
- **On Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **On macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Chromium Browser
Install the Chromium browser binary required for headless crawling:
```bash
playwright install chromium
```

---

## 🔑 Environment Variables Configuration

Copy `.env.example` to create your local `.env` file:

- **Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
- **macOS / Linux:**
  ```bash
  cp .env.example .env
  ```

Open `.env` in your text editor and provide your API key:

```ini
# Google Gemini API key (Recommended)
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI API key (Optional)
OPENAI_API_KEY=

# Groq API key (Optional)
GROQ_API_KEY=

# Model settings
DEFAULT_PROVIDER=gemini
GEMINI_MODEL=gemini-3.6-flash
OPENAI_MODEL=gpt-4o-mini
GROQ_MODEL=llama-3.3-70b-versatile

# Crawler Settings
HEADLESS=true
MAX_SUBPAGES_PER_DOMAIN=5
PAGE_TIMEOUT_MS=15000
```

> **Note**: You can also enter or switch your API key directly in the Streamlit web dashboard sidebar at runtime.

---

## 💻 How to Run Locally

### Option A: Interactive Web UI (Streamlit)
Launch the Streamlit dashboard:
```bash
streamlit run app.py
```
Open **`http://localhost:8501`** in your browser:
1. Paste your API key in the sidebar (if not already set in `.env`).
2. Enter target domains (comma-separated or one per line, e.g. `postman.com, supabase.com, vapi.ai`).
3. Click **🚀 Run Targets**.
4. Watch the live agent stream, review the **Summary Table**, and download data in **JSON** or **CSV** formats under **Export Data**.

### Option B: Command-Line Interface (CLI)
Run against the default benchmark targets (`postman.com`, `supabase.com`, `vapi.ai`):
```bash
python main.py
```

Run against custom target domains:
```bash
python main.py --domains stripe.com linear.app vercel.com --output output/leads.json
```

CLI options:
- `--domains`: Space-separated list of domains to enrich.
- `--output`: Filepath to save JSON results (defaults to `output/results.json`).
- `--provider`: LLM provider (`gemini`, `openai`, `groq`).
- `--subpages`: Maximum subpages to crawl per domain (default: `5`).
- `--no-headless`: Run Chromium in visible window mode.
- `--no-search`: Disable external search fallback.

---

## 🧪 Running Unit Tests

Run the automated test suite with Python's built-in `unittest`:
```bash
python -m unittest discover -s tests
```

Tests validate:
- HTML sanitization and boilerplate removal.
- Token reduction ratios (~85%–95%).
- Email and phone number regex extraction.
- Contact link discovery.
- Strict Pydantic schema validation.
- Subpage discovery and prioritization.

---

## 📤 Uploading to GitHub

To push this project to your GitHub account:

```bash
# 1. Initialize git repository
git init

# 2. Add all project files (secrets in .env are automatically excluded by .gitignore)
git add .

# 3. Create your initial commit
git commit -m "feat: initial commit of autonomous lead enrichment agent"

# 4. Rename main branch
git branch -M main

# 5. Link your GitHub remote repository
git remote add origin https://github.com/your-username/lead-enrichment-agent.git

# 6. Push to GitHub
git push -u origin main
```

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
