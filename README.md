# Member Intelligence — Ask Your Data

![Demo](docs/demo.gif)
<!-- Replace docs/demo.gif with a screen recording once deployed -->

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.56-FF4B4B?logo=streamlit&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Haiku%204.5-D97706?logo=anthropic&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly-6.6-3F4F75?logo=plotly&logoColor=white)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white)

Ask plain-English questions about your credit union data. Claude translates them into pandas expressions, runs them against your data, and renders an interactive chart — no SQL, no code, no BI tool required.

---

## Try these questions right now

These are ready to paste into the app and demonstrate the full range of the system:

| Audience | Question |
|---|---|
| **Executive** | `What is our loan-to-share ratio by month?` |
| **Executive** | `Show total deposit balances by member segment` |
| **Marketing** | `Which member segment has the highest average balance?` |
| **Lending** | `What is the delinquency rate by loan type?` |
| **Operations** | `How are members distributed across zip codes?` |

---

## How it works

```
Your question
     │
     ▼
 Translator (Claude Haiku)
 Converts natural language → single-line pandas expression
     │
     ▼
 Executor (safe sandbox)
 Validates + runs the expression against parquet DataFrames
     │
     ▼
 Chart Builder (Claude Haiku)
 Chooses best chart type + axis mapping → Plotly Express figure
     │
     ▼
 Streamlit UI
 Renders interactive chart + expandable code + follow-up input
```

Two Claude calls per question — one for translation, one for chart spec selection — both using prompt caching to keep cost low on repeated questions.

---

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit 1.56 |
| AI | Anthropic Claude Haiku 4.5 |
| Data | pandas 2.3 + pyarrow (parquet) |
| Charts | Plotly Express 6.6 |
| Deploy | Railway (Nixpacks) |

---

## Project structure

```
cu_nl_charts/
├── app.py                  # Streamlit UI
├── engine/
│   ├── translator.py       # Claude: question → pandas expression
│   ├── executor.py         # Safe eval sandbox
│   └── chart_builder.py    # Claude: DataFrame → Plotly figure
├── data/
│   ├── demo_data.py        # Generate synthetic CU dataset
│   ├── members.parquet
│   ├── accounts.parquet
│   ├── loans.parquet
│   └── monthly_balances.parquet
├── docs/
│   └── deploy.md           # Railway deploy guide
├── requirements.txt
├── railway.json
└── Procfile
```

---

## Quick start (local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# 3. Generate demo data
python data/demo_data.py

# 4. Run
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501).

---

## Deploy to Railway

See [docs/deploy.md](docs/deploy.md) for the full step-by-step guide.

```bash
railway login && railway init
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway up
```

---

## Demo dataset

The synthetic dataset models a mid-size credit union with realistic distributions:

| Table | Rows | Key columns |
|---|---|---|
| `members` | 2,000 | member_id, age, segment, zip_code, member_since |
| `accounts` | 3,200 | account_id, member_id, type, balance, status |
| `loans` | 1,400 | loan_id, member_id, type, balance, rate, status |
| `monthly_balances` | 12,000 | member_id, month, avg_balance, product_count |

Member segments: Youth · Young Adult · Prime · Established · Senior  
Loan types: auto · mortgage · personal · heloc  
Account types: checking · savings · cd · money_market

---

## Security

The executor runs Claude-generated pandas expressions in a restricted sandbox:

- `__builtins__` replaced with an explicit allowlist (no `open`, `exec`, `import`, etc.)
- Static regex scan rejects `os`, `sys`, `subprocess`, dunder access, and other escape vectors before `eval`
- Expressions must return a DataFrame or Series — scalars and other types are rejected
- Multi-line code is rejected; only single-line expressions are allowed

---

## License

MIT
# NL-Chart-Generator
