"""
Build a Plotly chart from a result DataFrame using Claude to choose the chart spec.
"""

import json

import anthropic
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_client = anthropic.Anthropic()
_MODEL = "claude-haiku-4-5"

_CU_BLUES = [
    "#003087", "#1B5EC8", "#3B7DD8", "#6FA3E8",
    "#9EC4F4", "#C4DCF9", "#E8F2FD",
]

_CHART_SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "chart_type": {
            "type": "string",
            "enum": ["bar", "line", "scatter", "pie", "histogram"],
        },
        "x": {"type": "string"},
        "y": {"type": "string"},
        "color": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "title": {"type": "string"},
    },
    "required": ["chart_type", "x", "y", "color", "title"],
    "additionalProperties": False,
}

_SYSTEM = """\
You are a data visualization advisor for a credit union analytics dashboard.

Given a question and a summary of the result DataFrame, choose the best chart type \
and axis mapping. Return a JSON object matching the schema exactly — no explanation, \
no prose, only the JSON.

Chart type guide:
- bar: comparisons across categories (counts, sums, averages by group)
- line: trends over time (monthly, yearly)
- scatter: relationships between two continuous variables
- pie: part-of-whole composition (≤ 6 categories only)
- histogram: distribution of a single continuous variable

Rules:
1. x and y must be exact column names from the DataFrame columns listed below.
2. color must be an exact column name or null.
3. For histogram, x is the column to distribute and y should be the same column.
4. title should be a concise, human-readable chart title derived from the question.
"""


def _df_summary(df: pd.DataFrame) -> str:
    lines = [
        f"Columns: {list(df.columns)}",
        f"Rows: {len(df)}",
        f"Dtypes: { {col: str(dt) for col, dt in df.dtypes.items()} }",
    ]
    if len(df) <= 5:
        lines.append(f"Data:\n{df.to_string(index=False)}")
    else:
        lines.append(f"Sample (first 3 rows):\n{df.head(3).to_string(index=False)}")
    return "\n".join(lines)


def _get_chart_spec(df: pd.DataFrame, question: str) -> dict:
    user_content = f"Question: {question}\n\nDataFrame summary:\n{_df_summary(df)}"

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _CHART_SPEC_SCHEMA,
            }
        },
        messages=[{"role": "user", "content": user_content}],
    )

    return json.loads(response.content[0].text)


def _apply_cu_theme(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        colorway=_CU_BLUES,
        title={
            "text": title,
            "x": 0.5,
            "xanchor": "center",
            "font": {"color": "#003087", "size": 18, "family": "Inter, Arial, sans-serif"},
        },
        font={"family": "Inter, Arial, sans-serif", "color": "#1A1A2E"},
        xaxis={
            "gridcolor": "#EEF2F7",
            "linecolor": "#D0D8E8",
            "title_font": {"color": "#003087"},
        },
        yaxis={
            "gridcolor": "#EEF2F7",
            "linecolor": "#D0D8E8",
            "title_font": {"color": "#003087"},
        },
        legend={"bgcolor": "rgba(0,0,0,0)"},
        margin={"t": 60, "b": 40, "l": 40, "r": 20},
    )
    return fig


def _safe_col(spec_value: str | None, columns: list[str]) -> str | None:
    """Return spec_value if it's a valid column name, else None."""
    if spec_value and spec_value in columns:
        return spec_value
    return None


def build_chart(df: pd.DataFrame, question: str) -> go.Figure:
    """
    Build a Plotly figure for a result DataFrame using Claude to choose the spec.

    Args:
        df:       Aggregated result DataFrame from safe_execute().
        question: Original natural-language question (used for chart title context).

    Returns:
        A styled Plotly go.Figure ready to display in Streamlit.

    Raises:
        ValueError: if the DataFrame is empty or Claude returns an unusable spec.
    """
    if df.empty:
        raise ValueError("Cannot build a chart from an empty DataFrame.")

    spec = _get_chart_spec(df, question)

    chart_type = spec["chart_type"]
    title = spec["title"]
    cols = list(df.columns)

    x = _safe_col(spec.get("x"), cols)
    y = _safe_col(spec.get("y"), cols)
    color = _safe_col(spec.get("color"), cols)

    # Fallback: if x/y are missing, use first two columns
    if x is None:
        x = cols[0]
    if y is None and len(cols) > 1:
        y = cols[1]
    elif y is None:
        y = cols[0]

    if chart_type == "bar":
        fig = px.bar(df, x=x, y=y, color=color, color_discrete_sequence=_CU_BLUES)

    elif chart_type == "line":
        fig = px.line(df, x=x, y=y, color=color, color_discrete_sequence=_CU_BLUES,
                      markers=True)

    elif chart_type == "scatter":
        fig = px.scatter(df, x=x, y=y, color=color, color_discrete_sequence=_CU_BLUES)

    elif chart_type == "pie":
        fig = px.pie(df, names=x, values=y, color_discrete_sequence=_CU_BLUES)

    elif chart_type == "histogram":
        fig = px.histogram(df, x=x, color=color, color_discrete_sequence=_CU_BLUES)

    else:
        # Fallback to bar for any unrecognised type
        fig = px.bar(df, x=x, y=y, color=color, color_discrete_sequence=_CU_BLUES)

    return _apply_cu_theme(fig, title)
