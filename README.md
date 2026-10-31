# Health Insights – Python Skills Assessment

A Streamlit + Python + SQLite patient-record application for the Gokul Infocare Task 2 assessment.

## Features
- Create, read, update and delete patient records.
- Validate email format, date of birth and numeric blood-test inputs.
- Accept `DD/MM/YYYY` and `DD.MM.YYYY` dates. The latter is accepted because the supplied assessment table uses dotted dates.
- Persist records in SQLite.
- Generate cautious, non-diagnostic AI remarks using an OpenAI-compatible API.
- Keep API credentials in `.env`, not in source control.

## Setup (Windows / macOS / Linux)
1. Install Python 3.10 or newer.
2. Extract this project and open a terminal in the project folder.
3. Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and add your API key:
   - `OPENAI_API_KEY=...`
   - Optional `OPENAI_MODEL=gpt-4o-mini`
6. Run: `streamlit run app.py`

If the API key is absent, the application clearly marks AI remarks as not configured. For the assessment's live API integration demonstration, configure a valid key before creating the valid test records.

## Assessment data handling
Enter the ten rows exactly as supplied in the PDF. Do not silently correct any values.
Expected validation failures:
- Test 2, John Hunter: `hunter@gmail` has no valid domain suffix.
- Test 4, Peter Larry: `31.11.2001` is not a real calendar date (November has 30 days).
- Test 8, Kris Wu: `19.10.2030` is a future DOB and `Kris.wu.gmail.com` is not a valid email address.
The remaining seven rows are valid under the application's basic format checks, subject to current date and successful API configuration. The duplicate Robyn Pears row is intentionally accepted as a separate record; records use unique database IDs.

## CRUD demonstration
- Create: use **Add Patient** and enter each supplied row without changing it.
- Read: use **View / Manage Records** and show the complete list.
- Update: select one record and change its email to `gokul@infocare.com`.
- Delete: select one record, confirm deletion, then show the refreshed list.

## AI integration
`generate_ai_remarks()` calls `https://api.openai.com/v1/chat/completions` with a model and prompt. The prompt prohibits diagnosis and asks the API to explain that interpretation depends on units, fasting status, age, sex, medical history and laboratory reference ranges. The API key is read from the environment; it is not hard-coded.

This prototype is not a validated medical device. The assessment PDF does not specify units or clinical reference ranges, so the application must not claim a definitive diagnosis or a medically validated risk score.

## GitHub upload
Before pushing:
1. Confirm `.env` is not staged: `git status`.
2. Never commit API keys, patient data or the generated `patients.db`.
3. Commit source files only.
4. Add screenshots/video separately only if they contain no real personal or confidential data.

Example:
```bash
git init
git add app.py requirements.txt README.md .env.example .gitignore
git commit -m "Build health insights assessment app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/health-insights-assessment.git
git push -u origin main
```

## Limitations
- The app stores data locally in SQLite; this is suitable for a small assessment demo, not a production multi-user clinical system.
- AI remarks are educational text, not diagnosis or treatment advice.
- If the external API is unavailable, the app displays the API error and does not save the record, so the user can retry.
