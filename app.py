"""
cu_nl_charts — Streamlit UI: Member Intelligence — Ask Your Data
"""

import os
from pathlib import Path

import anthropic
import pandas as pd
import streamlit as st

# Streamlit Cloud does NOT inject secrets as OS environment variables.
# translator.py and chart_builder.py call anthropic.Anthropic() at module
# import time, which reads from os.environ — so we must copy the key across
# before those imports execute.
if "ANTHROPIC_API_KEY" in st.secrets and "ANTHROPIC_API_KEY" not in os.environ:
    os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

from engine.chart_builder import build_chart  # noqa: E402
from engine.executor import safe_execute  # noqa: E402
from engine.translator import translate_question  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Member Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_DATA_DIR = Path(__file__).parent / "data"
_MODEL = "claude-haiku-4-5"
_DATA_DATE = "April 26, 2026"

_EXAMPLES: dict[str, list[str]] = {
    "🏛️  Executive": [
        "What is our loan-to-share ratio by month?",
        "Show total deposit balances by member segment",
        "What is the month-over-month average balance trend?",
    ],
    "📣  Marketing": [
        "Which member segment has the highest average balance?",
        "How are members distributed across zip codes?",
        "What is the age distribution of our members?",
    ],
    "💳  Lending": [
        "What is the delinquency rate by loan type?",
        "What is the average loan balance by loan type?",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] > .main { background: #F8FAFC; }
    [data-testid="stSidebar"]          { background: #FFFFFF; }

    .cu-header {
        background: linear-gradient(135deg, #003087 0%, #1B5EC8 100%);
        color: white;
        padding: 1.4rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 10px rgba(0,48,135,0.18);
    }
    .cu-header h1 {
        margin: 0;
        font-size: 1.65rem;
        font-weight: 700;
        letter-spacing: -0.3px;
    }
    .cu-header p {
        margin: 0.3rem 0 0;
        opacity: 0.82;
        font-size: 0.88rem;
    }

    .sidebar-group {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #6B7280;
        padding: 0.9rem 0 0.25rem;
    }

    .cu-footer {
        margin-top: 2.5rem;
        padding-top: 0.8rem;
        border-top: 1px solid #E2E8F0;
        color: #9CA3AF;
        font-size: 0.74rem;
        display: flex;
        justify-content: space-between;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data
def _load_data() -> tuple[dict[str, pd.DataFrame], dict[str, list[str]]]:
    names = ["members", "accounts", "loans", "monthly_balances"]
    dfs = {name: pd.read_parquet(_DATA_DIR / f"{name}.parquet") for name in names}
    schema = {name: list(df.columns) for name, df in dfs.items()}
    return dfs, schema


try:
    dataframes, schema = _load_data()
except FileNotFoundError:
    st.error(
        "Demo data not found. Run `python data/demo_data.py` first.",
        icon="🗄️",
    )
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Claude helper — rephrase suggestion on error
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource
def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _rephrase_suggestion(question: str, error: str) -> str | None:
    schema_text = "\n".join(
        f"  {t}: {', '.join(cols)}" for t, cols in schema.items()
    )
    try:
        resp = _anthropic_client().messages.create(
            model=_MODEL,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'The user asked: "{question}"\n\n'
                        f"This failed with: {error}\n\n"
                        f"Available tables and columns:\n{schema_text}\n\n"
                        "In 1–2 sentences, explain why the question was ambiguous "
                        "or what data was unavailable, then suggest a clearer rephrasing."
                    ),
                }
            ],
        )
        return resp.content[0].text.strip()
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "question_input": "",
    "followup_input": "",
    "auto_run": False,
    "last_result": None,    # dict{question, code, df, fig}
    "last_error": None,     # dict{question, error, suggestion}
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def _run(q: str) -> None:
    """Translate → execute → build chart. Writes result/error to session state."""
    st.session_state.last_result = None
    st.session_state.last_error = None

    with st.spinner("Translating question…"):
        try:
            code = translate_question(q, schema, dataframes)
        except Exception as exc:
            st.session_state.last_error = {
                "question": q, "error": str(exc), "suggestion": None,
            }
            return

    with st.spinner("Running query…"):
        try:
            df = safe_execute(code, dataframes)
        except ValueError as exc:
            suggestion = _rephrase_suggestion(q, str(exc))
            st.session_state.last_error = {
                "question": q, "error": str(exc), "suggestion": suggestion,
            }
            return

        if df.empty:
            error_msg = f"Query returned no rows.\n\nGenerated expression: `{code}`"
            suggestion = _rephrase_suggestion(q, error_msg)
            st.session_state.last_error = {
                "question": q, "error": error_msg, "suggestion": suggestion,
            }
            return

    with st.spinner("Building chart…"):
        try:
            fig = build_chart(df, q)
        except Exception as exc:
            suggestion = _rephrase_suggestion(q, str(exc))
            st.session_state.last_error = {
                "question": q, "error": str(exc), "suggestion": suggestion,
            }
            return

    st.session_state.last_result = {
        "question": q, "code": code, "df": df, "fig": fig,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def _pick_example(q: str) -> None:
    """on_click callback: load an example question and trigger auto-run."""
    st.session_state.question_input = q
    st.session_state.followup_input = ""
    st.session_state.auto_run = True
    st.session_state.last_result = None
    st.session_state.last_error = None


with st.sidebar:
    st.markdown("### 💡 Example Questions")
    st.caption("Click any question to run it instantly.")

    for _group, _qs in _EXAMPLES.items():
        st.markdown(
            f'<div class="sidebar-group">{_group}</div>', unsafe_allow_html=True
        )
        for _q in _qs:
            st.button(
                _q,
                key=f"ex_{hash(_q)}",
                use_container_width=True,
                on_click=_pick_example,
                args=(_q,),
            )

    st.divider()
    st.markdown("**Data tables**")
    for _name, _df in dataframes.items():
        _preview = ", ".join(list(_df.columns)[:3])
        if len(_df.columns) > 3:
            _preview += "…"
        st.caption(f"**{_name}** · {len(_df):,} rows  \n`{_preview}`")

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="cu-header">
        <h1>📊 Member Intelligence — Ask Your Data</h1>
        <p>Type a plain-English question about your credit union data. Claude translates it to a chart.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Question input
# ─────────────────────────────────────────────────────────────────────────────
col_q, col_btn = st.columns([5, 1])
with col_q:
    st.text_input(
        "question",
        placeholder="e.g. Which zip codes have the most members?",
        label_visibility="collapsed",
        key="question_input",
    )
with col_btn:
    submit = st.button(
        "Generate Chart",
        type="primary",
        use_container_width=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Trigger pipeline
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.auto_run and st.session_state.question_input.strip():
    st.session_state.auto_run = False
    _run(st.session_state.question_input.strip())
elif submit and st.session_state.question_input.strip():
    _run(st.session_state.question_input.strip())

# ─────────────────────────────────────────────────────────────────────────────
# Error display
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.last_error:
    _err = st.session_state.last_error
    st.error(f"**Could not generate chart**\n\n{_err['error']}")
    if _err.get("suggestion"):
        st.info(f"**💡 Rephrase suggestion**\n\n{_err['suggestion']}")

# ─────────────────────────────────────────────────────────────────────────────
# Results: chart + code + follow-up
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.last_result:
    _res = st.session_state.last_result

    st.plotly_chart(_res["fig"], use_container_width=True, theme=None)

    with st.expander("🔍 View pandas expression"):
        st.code(_res["code"], language="python")

    # ── Follow-up ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Ask a follow-up question")

    col_fu, col_fu_btn = st.columns([5, 1])
    with col_fu:
        st.text_input(
            "followup",
            placeholder="e.g. Break that down by account type",
            label_visibility="collapsed",
            key="followup_input",
        )
    with col_fu_btn:
        fu_submit = st.button(
            "Go",
            key="btn_followup",
            use_container_width=True,
        )

    if fu_submit and st.session_state.followup_input.strip():
        _followup_q = st.session_state.followup_input.strip()
        _context_q = (
            f'Follow-up to: "{_res["question"]}"\n'
            f"Previous pandas expression: {_res['code']}\n"
            f"New question: {_followup_q}"
        )
        st.session_state.question_input = _followup_q
        st.session_state.followup_input = ""
        _run(_context_q)
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="cu-footer">
        <span>Model: {_MODEL}</span>
        <span>Data as of {_DATA_DATE}</span>
    </div>
    """,
    unsafe_allow_html=True,
)
