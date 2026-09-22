# Drawing Office Dashboard — Version 1

A mobile-friendly, shareable Streamlit dashboard for the Drawing Office.

## Pages
- Overview
- Monthly Performance
- Draughtsmen
- Jobs
- Drawing Output
- Live Workload

## Implemented rules
- New + Release = New
- Release-only = Release
- Common release spelling variants are normalized
- Shared jobs: `ceil(total drawings / assigned draughtsmen)` per person
- Company totals use actual drawing count
- Person-level metrics use credited drawing counts
- Repeat job numbers are flagged

## Run locally
1. Install Python 3.11+
2. Open a terminal in this folder
3. `python -m venv .venv`
4. Windows: `.venv\Scripts\activate`
5. `pip install -r requirements.txt`
6. `streamlit run app.py`

Without Odoo secrets the app opens with sample data.

## Connect Odoo
Create `.streamlit/secrets.toml`:

```toml
[odoo]
url = "https://ultra-gear1.odoo.com"
db = "YOUR_DATABASE_NAME"
username = "YOUR_INTEGRATION_USER"
api_key = "YOUR_API_KEY"
project_id = 2
```

Use a dedicated read-only integration user and never commit the real secrets file.

## Share on phone and laptop
Deploy this folder to Streamlit Community Cloud, Render, Railway, Azure, AWS, or a company server.  
Then share the HTTPS link. On a phone, use "Add to Home Screen".

## Important stage-history note
The first version can use current stage and completion timestamps. Exact historical stage timing still needs old-stage/new-stage history from Odoo. Once exposed, that can replace the first-stage-change placeholder.
