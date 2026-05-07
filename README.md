# MonkAudit

MonkAudit is a simple internal Streamlit app for GrowingMonk prospect mini-audits and due diligence reports.

It helps the internal sales team collect prospect details, check basic website performance through Google PageSpeed Insights, run public/client-access research when available, and generate practical Markdown/PDF reports using Gemini through Vertex AI.

MonkAudit is internal-only. Customers do not log in, access the app, or use a dashboard. The GrowingMonk team runs the audit and shares only the client-safe Growth Due Diligence Report with prospects.

## Setup

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

### Mac/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Secrets

Copy the example secrets file:

```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

On Windows PowerShell:

```powershell
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
```

Then edit `.streamlit/secrets.toml`:

```toml
APP_PASSWORD = "change-this-password"
GOOGLE_CLOUD_PROJECT = "your-google-cloud-project-id"
GOOGLE_CLOUD_LOCATION = "asia-south1"
GEMINI_MODEL = "gemini-2.5-flash"
PAGESPEED_API_KEY = ""
GOOGLE_MAPS_API_KEY = ""
SERPAPI_API_KEY = ""

# Optional client analytics access
GA4_PROPERTY_ID = ""
SEARCH_CONSOLE_SITE_URL = ""

# Optional delivery features
GOOGLE_DRIVE_FOLDER_ID = ""
SMTP_HOST = ""
SMTP_PORT = "587"
SMTP_SECURITY = "starttls"
SMTP_USER = ""
SMTP_PASSWORD = ""
SMTP_FROM = ""
```

`PAGESPEED_API_KEY` is optional. PageSpeed may still work without it, but usage can be limited.
`GOOGLE_MAPS_API_KEY` is required for verified Google Places data in Deep Research Mode.
`SERPAPI_API_KEY` is optional. If it is missing, MonkAudit shows manual search queries instead of running paid search.

Never commit real secrets. `.streamlit/secrets.toml` is ignored by git.

## Using Vertex AI / ADC

MonkAudit uses Gemini through Vertex AI with Google Application Default Credentials. No Gemini API key is needed for this setup.

Before generating audits locally:

1. Install the Google Cloud CLI.
2. Log in:

```bash
gcloud auth login
```

3. Set your project:

```bash
gcloud config set project YOUR_PROJECT_ID
```

4. Create Application Default Credentials:

```bash
gcloud auth application-default login
```

5. Enable the Vertex AI API in the Google Cloud project.
6. Add these values to `.streamlit/secrets.toml`:

```toml
GOOGLE_CLOUD_PROJECT = "YOUR_PROJECT_ID"
GOOGLE_CLOUD_LOCATION = "asia-south1"
GEMINI_MODEL = "gemini-2.5-flash"
```

7. Run the app:

```bash
streamlit run app.py
```

Do not commit `.streamlit/secrets.toml`. For deployment later, use a service account or hosting provider environment credentials, not local ADC.

If Windows says `gcloud` is not recognized, install the Google Cloud CLI first, then open a new PowerShell window so PATH updates are loaded.

If using GA4 or Search Console client-access research, enable the relevant APIs and create ADC credentials with read-only scopes:

```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/webmasters.readonly"
```

If using Google Drive upload, enable the Google Drive API and create ADC credentials with the Drive file scope:

```bash
gcloud services enable drive.googleapis.com
```

```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.file"
```

If the Drive API was enabled recently, wait a few minutes before retrying the upload.

If Drive upload shows `Request had insufficient authentication scopes`, your existing local ADC login was created without the Drive scope. Re-run the command above, approve the new scopes in the browser, then restart Streamlit.

If you need both client-access analytics and Google Drive upload, include all scopes in one login:

```bash
gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/webmasters.readonly,https://www.googleapis.com/auth/drive.file"
```

## Run

From the `monkaudit` folder:

```bash
streamlit run app.py
```

You should see a password screen first. After login, a GrowingMonk team member enters prospect details and generates the audit reports.

## v3 Modes

MonkAudit has two internal modes:

- Quick Audit Mode: keeps the original v1 flow with manual inputs, PageSpeed, Gemini, and Markdown download.
- Deep Research Mode: uses Google Places, PageSpeed, website snapshot, optional SerpAPI search, manual search suggestions, contact discovery, competitor comparison, optional client-access analytics, and Gemini to create multiple sales-ready reports from the same research data.

Deep Research Mode needs `GOOGLE_MAPS_API_KEY` for verified Places data. If `SERPAPI_API_KEY` is missing, MonkAudit skips automated public web search and still produces manual search queries for the salesperson or strategist.

Google Places may return only a limited public review sample. Treat review themes as directional, not exhaustive. Do not make revenue, booking, or performance claims unless the client confirms the underlying data.

## Deep Research Outputs

Deep Research Mode generates separate documents from the same verified research data:

- Client-Shareable Growth Due Diligence Report: safe to share with prospects. It uses careful language, separates verified public data from inferred opportunities, and avoids harsh competitor framing or unsupported claims.
- Internal Sales Diligence Report: GrowingMonk internal-only. It can include pitch angle, outreach messages, call questions, competitor gaps, objections, internal cautions, access requests, and what not to claim.
- Sales Call Brief: a concise internal call-prep document.

The sales team should share only the Growth Due Diligence Report with prospects unless a strategist manually reviews and approves any other material.

For leads who have not signed yet, the client-shareable report should prove research quality without giving away the full execution playbook. Include the verified snapshot, strengths, visible opportunities, business implications, high-level Growth Sprint roadmap, tracking/access notes, and a clear next step. Avoid internal warnings, sales objections, outreach scripts, exact ad setup, detailed campaign structure, full content calendars, pricing strategy, or aggressive competitor language.

MonkAudit also asks for the prospect's business structure so the audit is framed correctly. Use `Single location/store` for a normal local outlet, `Local brand with multiple locations` for an owned multi-location business, `Regional master franchise` for territory/franchise expansion responsibilities, `Franchise location` for one operator inside a larger franchise system, and `Online-first brand` when local map visibility is secondary.

## Auto-Discovery Workflow

For Deep Research Mode, the user can start with only:

- Business name
- City / country or area

Optional fields are treated as overrides. Leave website, Instagram, contact, Google Maps link, and niche blank when unknown. MonkAudit will try to discover public data through Google Places, website snapshot, optional SerpAPI, and public contact signals.

The raw JSON keeps:

- `discovered_data`
- `manual_overrides`
- `final_data_used`

Reports use `final_data_used` as the main business identity and should clearly separate auto-discovered data, manual overrides, missing data, and anything that requires client access.

## v3 Client Access Research

Prospect Public Research uses public data only:

- Google Places
- PageSpeed
- Website snapshot
- Optional SerpAPI results if a key is configured
- Manual search query suggestions
- Public contact discovery
- Competitor comparison

Client Access Research is optional and should only be enabled when the prospect/client has given permission. It can use:

- GA4 Data API with `GA4_PROPERTY_ID`
- Search Console API with `SEARCH_CONSOLE_SITE_URL`

GA4 Data API requires the authenticated Google account or service account to have access to the GA4 property. Search Console API requires access to the Search Console property. Do not use analytics data without client permission, and do not claim revenue, bookings, or exact lead loss unless the client provides the data.

MonkAudit v3 includes:

- Website snapshot
- Optional GA4 access
- Optional Search Console access
- Manual search query suggestions
- Sales Call Brief
- Client-Shareable Growth Due Diligence Report
- Internal Sales Diligence Report

## PDF Export

MonkAudit uses `fpdf2` to generate PDF exports from generated Markdown reports.

Markdown remains the source of truth. PDF export is intended for internal sales review and prospect-friendly handoff of the client-safe due diligence report. If PDF generation fails because of formatting or environment issues, use the Markdown download.

PDF exports include GrowingMonk branding, headings, bullets, page numbers, and multi-page support.

Deep Research Mode provides these downloads:

- Sales Team Pack ZIP: internal sales diligence, sales call brief, client report copy, and verified research JSON.
- Customer Share Pack ZIP: client-safe Growth Due Diligence Report only.
- Client Due Diligence as PDF and Markdown
- Internal Sales Diligence as PDF and Markdown
- Sales Call Brief as PDF and Markdown
- Verified Research JSON

Download buttons are configured to avoid triggering a new report run. MonkAudit also keeps the last generated result in the active Streamlit session so a harmless page rerun does not immediately clear the reports.

The app shows a numbers and graphs summary for internal review, including available Google review counts, review gap indicators, PageSpeed scores, and visible competitor review-volume comparisons. These charts and comparison tables are also embedded into Deep Research PDF exports when the underlying data exists. Reports are prompted to include numeric snapshots and Markdown tables when the research data supports them.

## Sharing & Delivery

After Deep Research reports are generated, MonkAudit can optionally:

- Upload the client PDF, Customer Share Pack, or internal sales files to Google Drive.
- Email the selected PDF or ZIP attachment through SMTP.
- Save the audit to the internal Lead Pipeline & Audit History view.

These are internal-team actions only. They do not add customer login, customer app access, or a customer-facing dashboard.

Google Drive upload uses Application Default Credentials and the `drive.file` scope. Set `GOOGLE_DRIVE_FOLDER_ID` if uploads should land in a specific Drive folder; otherwise files upload to the authenticated account's My Drive. You can use the exact parent folder name `Sales-Reports`, paste the full folder URL, or use the long Drive folder ID.

For each upload, MonkAudit creates a new subfolder under the selected parent folder:

```text
Client_Name_YYYY-MM-DD_HH-MM
```

The selected PDF or ZIP is uploaded inside that client/timestamp folder.

Email delivery requires SMTP settings:

```toml
SMTP_HOST = "smtp.example.com"
SMTP_PORT = "587"
SMTP_SECURITY = "starttls"
SMTP_USER = "sender@example.com"
SMTP_PASSWORD = "app-password-or-smtp-password"
SMTP_FROM = "sender@example.com"
```

`SMTP_SECURITY` can be `starttls`, `ssl`, or `none`. If omitted, MonkAudit uses `ssl` for port `465` and `starttls` for other ports.

Use the client PDF or Customer Share Pack for prospects. Internal Sales Diligence, Sales Call Brief, and the Sales Enablement Pack are internal-only and should not be emailed to prospects.

## Lead Pipeline & Review Gate

MonkAudit saves generated audits to a local SQLite database by default:

```text
monkaudit/data/monkaudit.sqlite3
```

The `data/` folder is ignored by git. Set `MONKAUDIT_DB_PATH` in the hosting environment if the database should live on a mounted persistent disk. For multi-user production workflows, treat this as a lightweight internal tracker; migrate the same fields to HubSpot, Airtable, Google Sheets, or another CRM when the sales process grows.

Sales statuses:

- New
- Audited
- Contacted
- Replied
- Call Booked
- Won
- Lost

Prospect-shareable downloads, Drive uploads, and emails are locked until a GrowingMonk user confirms the client-facing review checkbox. This does not certify the report automatically; it records that a human reviewed the document for client-safe language, factual accuracy, and unsupported claims.

Drive upload has an optional "anyone with the link" sharing checkbox. Use it only for client-safe files after review.

PDF filenames:

- `Business_Name_Client_Growth_Due_Diligence_Report.pdf`
- `Business_Name_Internal_Sales_Diligence_Report.pdf`
- `Business_Name_Internal_Sales_Call_Brief.pdf`
- `Business_Name_GrowingMonk_Client_Share_Pack.zip`
- `Business_Name_GrowingMonk_Sales_Enablement_Pack.zip`
- `Business_Name_Verified_Research_Evidence_File.json`

## PDF Branding

PDF exports include a GrowingMonk header. To use the exact logo, place the logo file at:

```text
monkaudit/assets/growingmonk_logo.png
```

JPG and JPEG are also supported with the same base name. If no logo asset is present, MonkAudit uses a built-in GrowingMonk wordmark fallback so PDFs still look branded.

## Future Deployment Notes

Do not deploy real secrets from your local machine. For production, configure secrets in the hosting platform and keep `.streamlit/secrets.toml` local only.

Keep the simple in-app password gate for local/internal fallback use. For production protection, put Cloudflare Access in front of the app so only approved GrowingMonk users can reach it.

### Required Production Secrets

Set these as environment variables or platform secrets:

```toml
APP_PASSWORD = "strong-fallback-password"
GOOGLE_CLOUD_PROJECT = "google-cloud-project-id"
GOOGLE_CLOUD_LOCATION = "asia-south1"
GEMINI_MODEL = "gemini-2.5-flash"
PAGESPEED_API_KEY = "optional-google-pagespeed-key"
GOOGLE_MAPS_API_KEY = "google-maps-platform-key"
SERPAPI_API_KEY = "optional-serpapi-key"
GA4_PROPERTY_ID = "optional-ga4-property-id"
SEARCH_CONSOLE_SITE_URL = "optional-search-console-site-url"
GOOGLE_DRIVE_FOLDER_ID = "optional-google-drive-folder-id"
SMTP_HOST = "optional-smtp-host"
SMTP_PORT = "587"
SMTP_SECURITY = "starttls"
SMTP_USER = "optional-smtp-user"
SMTP_PASSWORD = "optional-smtp-password"
SMTP_FROM = "optional-sender-email"
```

`PAGESPEED_API_KEY` is optional, but recommended for more reliable PageSpeed API usage.

For hosted deployments, use a service account or platform-supported Google Cloud authentication. Do not commit service account JSON files. Prefer setting Google credentials through the hosting provider's secret manager.

### Render

Use a Render Web Service.

Recommended settings:

- Runtime: Python
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Root directory: `monkaudit` if deploying from a larger repository

Add `APP_PASSWORD`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL`, `GOOGLE_MAPS_API_KEY`, optional `PAGESPEED_API_KEY`, optional `SERPAPI_API_KEY`, and optional client-access IDs in Render environment variables. Configure Google Cloud credentials through Render secrets or a service account integration pattern appropriate for your Render plan.

To map `audit.growingmonk.com`, add a custom domain in Render, then create the DNS record Render provides in Cloudflare.

### Railway

Use a Railway service connected to the repository.

Recommended settings:

- Root directory: `monkaudit` if needed
- Install command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

Add `APP_PASSWORD`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL`, `GOOGLE_MAPS_API_KEY`, optional `PAGESPEED_API_KEY`, optional `SERPAPI_API_KEY`, and optional client-access IDs in Railway variables. Configure Google Cloud credentials through Railway variables/secrets. Do not commit credential files.

To map `audit.growingmonk.com`, add the custom domain in Railway and create the required DNS record in Cloudflare.

### Streamlit Community Cloud

Use Streamlit Community Cloud if the repository setup is acceptable for an internal tool.

Recommended settings:

- App file: `monkaudit/app.py`
- Python dependencies: `monkaudit/requirements.txt`
- Secrets: add values through Streamlit Community Cloud app secrets, not through a committed file

Streamlit Community Cloud custom domain support may depend on the current platform plan/features. If custom domain mapping is not available, use the Streamlit app URL behind Cloudflare where possible, or choose Render/Railway for simpler custom domain control.

### Cloudflare Access

Recommended production protection:

1. Put `audit.growingmonk.com` behind Cloudflare.
2. Create a Cloudflare Access application for `audit.growingmonk.com`.
3. Allow only approved GrowingMonk emails or your company identity provider.
4. Keep the app's simple `APP_PASSWORD` as a fallback layer, not the main production security layer.

This avoids adding complex authentication code to MonkAudit v1 while still keeping the internal tool protected.

### Custom Subdomain

Future target:

```text
audit.growingmonk.com
```

General flow:

1. Deploy the app on Render, Railway, or Streamlit Community Cloud.
2. Add `audit.growingmonk.com` as a custom domain in the hosting platform if supported.
3. In Cloudflare DNS, create the required `CNAME` or `A` record from the hosting platform.
4. Enable HTTPS.
5. Add Cloudflare Access protection before sharing the app internally.

# Deploying MonkAudit to Google Cloud Run

MonkAudit is an internal Streamlit tool. This deployment keeps the app internal behind its password gate and does not add customer login, a dashboard, a database, or payment.

Expected Cloud Run settings:

- Region: `asia-south1`
- Service name: `monkaudit`
- Runtime: container built from this repository
- Port: `$PORT`, default `8080`
- Streamlit address: `0.0.0.0`

## Environment Variables

Cloud Run should provide these values as environment variables. Local development can still use `.streamlit/secrets.toml`; the app checks Streamlit secrets first and environment variables second.

Required:

```text
APP_PASSWORD
GOOGLE_CLOUD_PROJECT
GOOGLE_CLOUD_LOCATION
GEMINI_MODEL
GOOGLE_MAPS_API_KEY
```

Expected or optional:

```text
PAGESPEED_API_KEY
SERPAPI_API_KEY
GA4_PROPERTY_ID
SEARCH_CONSOLE_SITE_URL
GOOGLE_DRIVE_FOLDER_ID
SMTP_HOST
SMTP_PORT
SMTP_SECURITY
SMTP_USER
SMTP_PASSWORD
SMTP_FROM
```

Defaults:

- `GOOGLE_CLOUD_LOCATION` defaults to `asia-south1`.
- `GEMINI_MODEL` defaults to `gemini-1.5-flash`.
- `SERPAPI_API_KEY`, `GA4_PROPERTY_ID`, and `SEARCH_CONSOLE_SITE_URL` are optional.
- `PAGESPEED_API_KEY` is optional; PageSpeed may still work without it, subject to API limits.
- `GOOGLE_MAPS_API_KEY` is required for verified Google Places data in Deep Research Mode. If missing, the app shows a clean warning/error for Places-dependent research.

MonkAudit uses Gemini through Vertex AI / Application Default Credentials. Do not configure direct Gemini API-key based access or alternate LLM provider credentials for this app.

## A. Local Test

From the `monkaudit` folder:

```bash
streamlit run app.py
```

Checklist:

- Login works
- Quick Audit works
- Deep Pitch Report works
- PDFs download
- Gemini Vertex works
- Google Places works

## B. Google Cloud Login And Project Setup

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region asia-south1
```

## C. Enable APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable places-backend.googleapis.com
gcloud services enable pagespeedonline.googleapis.com
```

Optional:

```bash
gcloud services enable analyticsdata.googleapis.com
gcloud services enable searchconsole.googleapis.com
```

If using Google Drive upload from Cloud Run, also enable:

```bash
gcloud services enable drive.googleapis.com
```

## D. Create Cloud Run Service Account

```bash
gcloud iam service-accounts create monkaudit-runner \
  --display-name="MonkAudit Cloud Run Service Account"
```

Grant Vertex AI access:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:monkaudit-runner@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## E. Deploy To Cloud Run In Mumbai

```bash
gcloud run deploy monkaudit \
  --source . \
  --region asia-south1 \
  --service-account monkaudit-runner@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars APP_PASSWORD="YOUR_STRONG_APP_PASSWORD" \
  --set-env-vars GOOGLE_CLOUD_PROJECT="YOUR_PROJECT_ID" \
  --set-env-vars GOOGLE_CLOUD_LOCATION="asia-south1" \
  --set-env-vars GEMINI_MODEL="gemini-1.5-flash" \
  --set-env-vars GOOGLE_MAPS_API_KEY="YOUR_GOOGLE_MAPS_API_KEY" \
  --set-env-vars PAGESPEED_API_KEY="YOUR_PAGESPEED_API_KEY" \
  --set-env-vars SERPAPI_API_KEY="" \
  --set-env-vars GA4_PROPERTY_ID="" \
  --set-env-vars SEARCH_CONSOLE_SITE_URL=""
```

`--allow-unauthenticated` is acceptable only because the app has its own password gate. For stronger protection, use Cloudflare Access later.

The included `deploy.sh` file contains the same deployment command as a template. Edit every `YOUR_*` placeholder before running it.

## F. Get Cloud Run URL

```bash
gcloud run services describe monkaudit \
  --region asia-south1 \
  --format="value(status.url)"
```

## G. Logs

```bash
gcloud run services logs read monkaudit \
  --region asia-south1 \
  --limit 100
```

## H. If Gemini Fails In asia-south1

If Vertex Gemini model is not available in `asia-south1`, keep Cloud Run in `asia-south1` but set:

```text
GOOGLE_CLOUD_LOCATION="us-central1"
```

Then redeploy.

# DNS Setup for audit.growingmonk.com

Cloudflare steps:

1. Copy the Cloud Run URL after deployment.

Example:

```text
https://monkaudit-xxxxx-asia-south1.a.run.app
```

2. In Cloudflare:

```text
Websites -> growingmonk.com -> DNS -> Records -> Add record
```

3. Add record:

```text
Type: CNAME
Name: audit
Target: monkaudit-xxxxx-asia-south1.a.run.app
Proxy status: DNS only first
TTL: Auto
```

Important: remove `https://` from the target.

4. Test:

```text
https://audit.growingmonk.com
```

5. If simple CNAME does not work, use a Cloudflare Worker fallback.

Worker code:

```js
export default {
  async fetch(request) {
    const upstream = "monkaudit-xxxxx-asia-south1.a.run.app";
    const url = new URL(request.url);
    url.hostname = upstream;
    url.protocol = "https:";

    const newRequest = new Request(url.toString(), request);
    return fetch(newRequest);
  },
};
```

Worker route:

```text
audit.growingmonk.com/*
```

# Security Notes

- MonkAudit is internal-only.
- Customers should not get app access.
- Share only the client-safe Growth Due Diligence PDF with prospects.
- Do not share the raw Cloud Run URL publicly.
- Use a strong `APP_PASSWORD`.
- Later, protect `audit.growingmonk.com` with Cloudflare Access.
- Allow only approved emails:
  - founder email
  - growth strategist email
  - sales/outreach email
- Never commit `.streamlit/secrets.toml`.
- Never commit API keys.
- Do not store private client analytics unless permission is given.

# Post-Deployment Checklist

After deployment:

- Open Cloud Run URL
- Test login
- Run Quick Audit
- Run Deep Pitch Report
- Generate Internal Sales Diligence PDF
- Generate Client Growth Due Diligence PDF
- Generate Sales Call Brief PDF
- Confirm PDF downloads work
- Confirm Google Places works
- Confirm Gemini works
- Confirm missing optional SerpAPI does not crash
- Confirm `audit.growingmonk.com` loads after DNS setup
- Confirm app is password protected
