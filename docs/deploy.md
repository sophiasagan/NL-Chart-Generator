# Deployment Guide — Railway

This guide takes the app from your local machine to a live public URL in under ten minutes.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| [Railway CLI](https://docs.railway.app/develop/cli) | `npm i -g @railway/cli` |
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| Python 3.11+ | Must match local dev environment |

---

## 1. Generate the demo data locally

The parquet files must exist before deploying — Railway will bundle them during the build step.

```bash
cd cu_nl_charts
python data/demo_data.py
```

Expected output: four files created in `data/` — `members.parquet`, `accounts.parquet`, `loans.parquet`, `monthly_balances.parquet`.

---

## 2. Log in and initialise the project

```bash
railway login
railway init
```

`railway init` will prompt you to either create a new project or link to an existing one. Choose **Create new project** and give it a name like `cu-nl-charts`.

---

## 3. Set environment variables

The only secret the app needs is your Anthropic API key.

```bash
railway variables set ANTHROPIC_API_KEY=sk-ant-...
```

To verify it was saved:

```bash
railway variables
```

You should see `ANTHROPIC_API_KEY` listed (value is masked).

> **Do not commit `.env` files or API keys to git.** The `.env.example` file in this repo shows the expected variable names without values.

---

## 4. Deploy

```bash
railway up
```

Railway will:
1. Detect the Nixpacks build environment from `requirements.txt`
2. Install Python dependencies
3. Bundle the `data/` parquet files
4. Start the app using the command in `railway.json`:  
   `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`

Build typically takes 2–3 minutes on first deploy (dependency install), under 30 seconds on subsequent deploys.

---

## 5. Get the public URL

```bash
railway domain
```

This prints your auto-assigned URL, e.g. `cu-nl-charts-production.up.railway.app`. You can also set a custom domain in the Railway dashboard under **Settings → Domains**.

---

## 6. Verify the deployment

Open the URL in a browser and confirm the health check passes:

```
https://<your-app>.up.railway.app/_stcore/health
```

Expected response: `ok`

---

## 7. Test with example questions

Paste each question into the app's text input and click **Generate Chart**. Verify a chart renders within ~5 seconds.

| # | Question | Expected chart |
|---|---|---|
| 1 | `Which member segment has the highest average balance?` | Bar chart — segments on x-axis, average balance on y-axis |
| 2 | `What is the age distribution of our members?` | Histogram — member ages |
| 3 | `What is the average loan balance by loan type?` | Bar chart — loan types vs. average balance |

If a question fails, the app will display the pandas error and a Claude-generated rephrase suggestion.

---

## 8. Redeploy after changes

```bash
# Make your changes, then:
railway up
```

Railway redeploys in-place. Zero-downtime deploys are automatic.

---

## Environment variables reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key — get one at console.anthropic.com |
| `PORT` | Set by Railway | HTTP port — injected automatically, do not set manually |

---

## Troubleshooting

**Build fails with `ModuleNotFoundError`**  
All dependencies are pinned in `requirements.txt`. If you've added a new import, add it to `requirements.txt` and redeploy.

**`Demo data not found` error on startup**  
The parquet files in `data/` were not bundled. Run `python data/demo_data.py` locally and redeploy with `railway up` — Railway bundles whatever is on disk at deploy time.

**Chart takes more than 10 seconds**  
Haiku is fast, but cold-start latency on the first request after a deploy can be higher. Subsequent requests are faster due to prompt caching on the system prompt.

**`ANTHROPIC_API_KEY` not found**  
Re-run `railway variables set ANTHROPIC_API_KEY=sk-ant-...` and redeploy. The variable must be set before the build, not after.
