# PromptCraft Hub

**Build better prompts. Get better results.**

PromptCraft Hub is a local, offline-capable web application that teaches prompt engineering by example. It does not just hand you a prompt: it explains **why it works**, shows **what is missing** in your own prompts, and shows **how to customise** them.

* **Node.js and npm are NOT required.** The project contains no `package.json`, no JavaScript build step, no frontend server and no second port. It is pure Python plus browser-native HTML, CSS and JavaScript.
* Everything runs on your computer at `http://127.0.0.1:8000`. No prompt data leaves your machine; there are no AI services, API keys, analytics or CDNs.

---

## 1. Main features

| Area | What you get |
|---|---|
| **Prompt Library** | 79 complete prompts in 16 categories (13 featured). Keyword search with suggestions and highlighting, category / subcategory / AI tool / difficulty / role / tag / featured filters that combine, 5 sort orders, grid and list views, pagination, result counts and no-results guidance. |
| **Prompt detail** | Prompt split into Role, Context, Task, Input, Output format, Constraints, Quality criteria; highlighted `[PLACEHOLDERS]`; customisation form with live preview; copy, favorite, duplicate, export (TXT / MD / JSON), printable view, local share URL, why it works, tips, common mistakes, related prompts, version, quality score. |
| **Prompt Builder** | 9-step "Prompt Blueprint" wizard with step validation, live preview, completion score, missing-section guidance, drafts (browser Local Storage), sample, reset, copy, save to My Prompts, export. |
| **Prompt Diagnostic** | Marks Role, Context, Task, Input, Output format, Constraints, Audience, Tone, Quality criteria and Specificity as *Present / Partially present / Missing / Needs clarification*; checks ambiguity, conflicting instructions and privacy indicators; recommendations; copy; download TXT / JSON; hand-off to the Improver. |
| **Prompt Improver** | Rule-based (no AI, no API key) rewrite into a structured prompt, side-by-side comparison, original vs improved score, changes and why each helps, edit and re-score, copy, save, export. |
| **Before & After** | 15 scenarios with weak prompt, problems, improved prompt, improvements, why it is better, expected output difference, score comparison, copy, "Try in Prompt Builder", "Diagnose weak prompt". |
| **Learning Center** | 16 lessons with objective, explanation, good and weak example, tips, mistakes, knowledge check, mark complete (progress saved), previous / next; 20-term glossary. |
| **Favorites / My Prompts** | Favorites with search and filters. My Prompts: create, edit, version history with restore, tags, categories, archive / restore, permanent delete (confirmed), export, search. |
| **Administration** | PIN-protected (first-run setup, salted PBKDF2 hash, signed cookie sessions with expiry, lockout after repeated failures). Create / edit / archive / restore / publish / feature prompts; manage categories, subcategories, tags, lessons, glossary and examples; JSON import with preview, validation, duplicate handling and error report; library export; usage statistics; import history; validation-error log; database backup. |
| **Quality scoring** | Transparent 0-100 score (task 20, context 15, role 10, input 10, output format 15, constraints 10, audience 5, quality criteria 10, specificity 5) with penalties for ambiguity, conflicting instructions and extremely short prompts. Labels: Needs Improvement, Basic, Good, Strong, Excellent. The score is rule-based and is **not** AI. |

## 2. Technology stack

Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic 2 / pydantic-settings, Jinja2, python-multipart, itsdangerous, SQLite (WAL mode), an internal schema-version migration mechanism, standard `logging`. Front end: server-rendered Jinja2 templates, hand-written CSS design system (light and dark), vanilla JavaScript with the Fetch API, a local SVG icon sprite. Tests: pytest and httpx.

## 3. Folder structure

```
PromptCraft-Hub/
├── app/
│   ├── api/            prompts, categories, favorites, custom_prompts, learning, examples,
│   │                   admin, import_export, health, system (settings/statistics), pages (HTML), deps
│   ├── core/           config, logging_config, security, exceptions, middleware, templating
│   ├── database/       connection, models, initialization, migrations
│   ├── schemas/        prompt, category, learning, improver, common
│   ├── services/       prompt, search, scoring, use_case_profiles, improver, builder, export,
│   │                   statistics, custom, learning, content, admin
│   ├── seed/           prompts.json, learning_modules.json, examples.json, glossary.json, seed_database.py
│   ├── templates/      base.html, pages, partials/, error pages (400/403/404/422/500)
│   ├── static/         css/, js/, icons/ (SVG sprite), images/, vendor/ (empty: nothing external is needed)
│   ├── utilities/      text_utils, validation, file_utils
│   └── main.py
├── data/               promptcraft.db is created here on first start
├── backups/            timestamped database backups
├── logs/               promptcraft.log
├── tests/              pytest suite (uses a temporary database)
├── scripts/            launcher, stop_server, smoke_test, initialize_database, backup_database,
│                       check_environment, reset_admin_pin, _prepare.bat (shared by the .bat files)
├── samples/            sample_prompt_import.json
├── setup_app.bat  start_app.bat  stop_app.bat  run_tests.bat  backup_data.bat
├── requirements.txt  .env.example  .gitignore  LICENSE.txt  README.md
```

## 4. Prerequisites

* Windows 10 or 11 (the Python code also runs on macOS and Linux).
* **Python 3.11 or later** from <https://www.python.org/downloads/> ("Add python.exe to PATH" ticked; "Install for me only" needs no administrator rights).
* An internet connection **only the first time**, to download the Python packages listed in `requirements.txt`. After that the application works fully offline.
* No Node.js, npm, Docker, administrator rights or global package installs.

## 5. First-time startup (single click)

1. Install Python 3.11 or later.
2. Extract the project (any folder, spaces are fine).
3. Double-click **`start_app.bat`**.
4. Wait for the browser to open (the first start creates `.venv`, installs packages, creates and seeds the database).
5. Use PromptCraft Hub at **http://127.0.0.1:8000** (API reference: **http://127.0.0.1:8000/docs**).

Keep the black server window open while you use the app.

`setup_app.bat` does the same preparation without starting the server and ends with a configuration check; it is optional.

### Manual start (optional)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts\launcher.py
```

### Stopping

Press `Ctrl+C` in the server window, or double-click **`stop_app.bat`**. It stops only the process that answers `/api/health` as "PromptCraft Hub" **and** matches the PID file (`data\promptcraft.pid`). Stale PID files are removed; unrelated processes (including other Python programs) are never touched.

If port 8000 is already used, `start_app.bat` checks who owns it. If it is PromptCraft Hub it simply opens the browser; if it is another program it explains what to do and stops nothing.

## 6. Tests

Double-click **`run_tests.bat`** (or `python -m pytest tests` and `python scripts\smoke_test.py`). The backend tests set a temporary database, backup and log folder **before** the app is imported, so your real `data\promptcraft.db` can never be touched. The smoke test checks the installed application read-only: structure, database, integrity, seed counts, health, pages, one prompt, CSS and JavaScript, template rendering.

## 7. Backups

Double-click **`backup_data.bat`** (or use *Administration → Create backup*). An integrity check runs first; the copy is made with SQLite's online backup API into `backups\promptcraft-backup-YYYYMMDD-HHMMSS.db`; existing backups are never overwritten. Backups contain all of your saved data: store them privately. To restore, stop the app and copy a backup over `data\promptcraft.db`.

## 8. Locations

| Item | Path |
|---|---|
| Database | `data\promptcraft.db` (created automatically; never overwritten on restart) |
| Logs | `logs\promptcraft.log` (rotating; no prompts, PINs or session values) |
| Backups | `backups\` |
| Local secret | `.env` (generated on first start; excluded from source control; never printed or logged) |

## 9. Import and export

* **Any prompt** can be exported as TXT, Markdown or JSON from its detail page, Favorites and My Prompts. Unicode is preserved.
* **Administration → Import / export**: choose a `.json` file (up to `MAX_IMPORT_FILE_MB`), choose how to handle duplicates (skip or update, matched by slug) and invalid prompts (abort everything, or skip the invalid ones), click *Preview and validate*, review the table, then *Import*. Aborted or partly skipped imports provide a downloadable error report. `samples\sample_prompt_import.json` shows the format.
* **Export library** downloads every prompt and category as one JSON file (re-importable).

## 10. Admin PIN

The first visit to **Administration** shows a setup screen: choose a PIN of at least 6 characters. Only a salted PBKDF2-SHA256 hash is stored. Sessions are signed HttpOnly, SameSite=Strict cookies that expire after `SESSION_EXPIRY_MINUTES`. Five wrong attempts lock sign-in for 5 minutes. Change the PIN in *Administration → Change PIN* (this signs out other sessions).

> Local PIN authentication is intended for a local demonstration. Replace it with enterprise authentication before deploying the application publicly.

## 11. Configuration

Settings come from environment variables or a `.env` file in the project folder (see `.env.example`). Environment variables win.

| Variable | Default | Meaning |
|---|---|---|
| `APP_NAME`, `APP_VERSION`, `APP_ENV` | PromptCraft Hub, 1.0.0, development | Identity |
| `HOST`, `PORT` | 127.0.0.1, 8000 | Keep `127.0.0.1` for local-only access |
| `DATABASE_URL` | `sqlite:///./data/promptcraft.db` | SQLite only in this version |
| `LOG_LEVEL` | INFO | Logging verbosity |
| `ENABLE_PROMPT_CONTENT_LOGGING` | false | Leave off: prompts are then never logged |
| `LOCAL_ADMIN_MODE` | true | Local PIN administration |
| `AUTO_OPEN_BROWSER` | true | Open the browser after start |
| `SESSION_EXPIRY_MINUTES` | 60 | Admin session lifetime |
| `MAX_IMPORT_FILE_MB` | 5 | Import size limit |
| `BACKUP_DIRECTORY` | `./backups` | Where backups go |
| `SECRET_KEY` | (blank) | Generated into `.env` on first start when blank |

Extra optional settings: `LOG_DIRECTORY`, `ALLOWED_HOSTS`, `CORS_ORIGINS`, `MAX_REQUEST_BODY_MB`, `PIN_MAX_ATTEMPTS`, `PIN_LOCK_MINUTES`, `COOKIE_SECURE`.

## 12. Security notes and limitations

Implemented: server-side validation (Pydantic and service rules), HTML escaping everywhere (highlighting is escape-first), strict Content-Security-Policy (`script-src 'self'`), security headers, CSRF protection (signed double-submit cookie plus Origin checks) on every state-changing request, trusted-host and CORS allow-lists limited to local origins, upload extension and size limits, request-size limit, safe export / backup file names, parameterised SQLAlchemy queries with escaped LIKE wildcards, salted PIN hashing with lockout, no external network calls, no prompt content in logs.

Limitations: it is a **single-user local demonstration**. There is one local profile, the PIN is not enterprise authentication, the database is not encrypted, and anyone who can use your Windows account can read the files. Serving it on a network or the internet needs real authentication, HTTPS (`COOKIE_SECURE=true`) and a hardened deployment. The scores, diagnostics and improvements are deterministic heuristics, useful guidance but not a guarantee of AI output quality.

## 13. Responsible AI guidance

> Do not enter confidential, personal, customer, financial, medical, or company-sensitive information unless your organization has approved the AI tool and the data-handling process.

Anonymise data with placeholders, ask the AI for assumptions and verification steps, verify facts and calculations, keep a person accountable for decisions, and watch for hallucinations and prompt injection in pasted text. When you want to see how an answer was reached, ask for a concise explanation, assumptions, sources and verification steps rather than hidden internal reasoning. The in-app Privacy page and lesson 16 cover this in more detail.

## 14. Troubleshooting

| Problem | What to do |
|---|---|
| **"Python is not recognized" / not installed** | Install Python 3.11+ from python.org with "Add python.exe to PATH", then reopen the script. If typing `python` opens the Microsoft Store, install from python.org. |
| **Python version is unsupported** | Install Python 3.11 or later. If `.venv` was created with an older Python, delete the `.venv` folder and run `start_app.bat` again. |
| **pip is missing** | Re-run the Python installer → Modify → tick *pip*. The scripts also try `python -m ensurepip` automatically. |
| **Virtual environment creation failed** | Make sure the folder is writable (move it to Documents), delete a half-created `.venv`, retry. |
| **Dependency installation failed** | Check internet, proxy and firewall; run the script again (downloads are reused). On a corporate network ask IT for a PyPI mirror. |
| **Port 8000 is already in use** | If it is PromptCraft Hub the browser just opens. Otherwise close the other program, or add `PORT=8010` to a `.env` file in the project folder. |
| **Database is locked** | Close other programs using `data\promptcraft.db` (DB browsers, a second copy of the app, antivirus scans) and retry; SQLite waits 8 seconds before reporting a lock and the app then shows a "temporarily unavailable" page. |
| **Browser did not open** | Open `http://127.0.0.1:8000` yourself. Check `AUTO_OPEN_BROWSER` is not `false`. |
| **Admin PIN is not working** | Five wrong attempts lock sign-in for 5 minutes. To remove a forgotten PIN: `.venv\Scripts\python scripts\reset_admin_pin.py` and type `YES`; you set a new PIN on the next visit. |
| **Cannot write to the project directory** | Move the folder out of Program Files / protected or synced-read-only locations (for example to Documents). |
| **Seed data was not loaded** | Run `.venv\Scripts\python scripts\initialize_database.py`. Seeding only fills **empty** tables and is skipped for content you deliberately deleted; add `--reseed` to fill tables that are empty even after having been seeded. |
| **Static files are not displayed** | Hard-refresh (Ctrl+F5). Make sure `app\static` is complete (re-extract the ZIP if not). Missing assets return a clear text message. |
| **Database backup failed** | Check free disk space and permissions on `backups\`; the integrity check must pass. Details are in `logs\promptcraft.log`. |

Every error page shows an actionable message; technical details go to `logs\promptcraft.log`, never to the browser.

## 15. Deploying a public demo on Render

This repository includes a `render.yaml` Blueprint for a free Render web service. To deploy:

1. Push the project to a GitHub repository (do not include `.env`, `.venv`, or files from `data/`).
2. In Render, choose **New → Blueprint**, connect that repository, and apply the `render.yaml` configuration.
3. Open `https://promptcraft-hub.onrender.com` after the first deployment and configure the administrator PIN immediately.

If you change the Render service name, update `ALLOWED_HOSTS` and `CORS_ORIGINS` in `render.yaml` to match its generated `*.onrender.com` hostname. The free service can sleep while idle, and its filesystem is ephemeral: the SQLite database, administrator PIN, and saved content may be lost on restart or redeploy. This is a shared public demo, not a private or multi-user service; do not enter sensitive information. For persistent data and real public use, choose a persistent database/storage plan and add proper user authentication before deployment.

## 16. Future deployment options and extension points

The code is layered (API → services → models) so these can be added without rewriting the UI: Microsoft Entra ID or other enterprise sign-in (replace `app/api/deps.py` and `AdminCredential`), multiple users and role-based access (`LocalProfile` already scopes favorites, progress and custom prompts), approval workflows and community submissions (`published` / `archived` flags), ratings, team workspaces, prompt analytics (`PromptUsageEvent`), PostgreSQL and full-text search (`search_service.py` is isolated), and AI-powered improvement: add a class next to `RuleBasedPromptImprover` that implements `PromptImproverProvider` (the `FutureAIProvider` stub marks the slot) and register it in `get_provider`. No paid API is implemented in this version.

## License

MIT, see `LICENSE.txt`.
