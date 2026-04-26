"""
Translate plain-English questions into single-line pandas expressions via Claude.
"""

import anthropic
import pandas as pd

_client = anthropic.Anthropic()

# Model choice: haiku-4-5 is fast and cost-effective for this narrow,
# structured translation task (called on every question).
# Swap to "claude-opus-4-7" for higher accuracy if needed.
_MODEL = "claude-haiku-4-5"

_SYSTEM_PREFIX = """\
You are a pandas code generator for a credit union analytics system.

Available DataFrames and their columns:
{schema_description}

Rules — you MUST follow all of them:
1. Return ONLY a single-line pandas expression. No imports, no variable \
assignments, no function definitions, no multi-line code, no markdown fences, \
no explanation, no trailing punctuation.
2. The expression MUST evaluate to a DataFrame or Series — never a scalar, \
never a list.
3. Use only the DataFrame names listed above plus standard pandas operations.
4. Column names that contain spaces or special characters must be quoted \
(e.g. df["my col"]).

Examples:
Q: How many members joined each year?
A: members.groupby(members.member_since.dt.year).size().reset_index(name="count")

Q: What is the average loan balance by loan type?
A: loans.groupby("type")["balance"].mean().reset_index(name="avg_balance")

Q: Which zip codes have the most members?
A: members.groupby("zip_code").size().reset_index(name="count").sort_values("count", ascending=False)

Q: What is the total checking balance per member segment?
A: accounts[accounts["type"] == "checking"].merge(members[["member_id", "segment"]], on="member_id").groupby("segment")["balance"].sum().reset_index(name="total_balance")

Q: Show average monthly balance trend over the last 6 months.
A: monthly_balances.groupby("month")["avg_balance"].mean().reset_index()

Q: What is the loan-to-share ratio by month?
A: monthly_balances.groupby("month")["avg_balance"].sum().reset_index(name="total_deposits").assign(total_loans=loans["balance"].sum(), loan_to_share_ratio=lambda d: (loans["balance"].sum() / d["total_deposits"]).round(4))

Q: Show total deposit balances by member segment.
A: accounts.merge(members[["member_id", "segment"]], on="member_id").groupby("segment")["balance"].sum().reset_index(name="total_balance")
"""


def _schema_description(schema: dict, dataframes: dict | None = None) -> str:
    lines = []
    for name, cols in schema.items():
        df = dataframes.get(name) if dataframes else None
        col_descs = []
        for col in cols:
            if df is not None and str(df[col].dtype) == "object":
                uniq = sorted(df[col].dropna().unique().tolist())
                if 1 < len(uniq) <= 12:
                    vals = ", ".join(f'"{v}"' for v in uniq)
                    col_descs.append(f'{col} (values: {vals})')
                    continue
            col_descs.append(col)
        lines.append(f"  {name}: {', '.join(col_descs)}")
    return "\n".join(lines)


def translate_question(question: str, schema: dict, dataframes: dict | None = None) -> str:
    """
    Convert a plain-English question into a single-line pandas expression.

    Args:
        question:   Natural-language question about the credit union data.
        schema:     Mapping of DataFrame name → list of column names.
        dataframes: Optional mapping of DataFrame name → pd.DataFrame.
                    When provided, categorical column values are included in
                    the schema description so Claude uses exact filter values.

    Returns:
        A single-line pandas expression (str) suitable for safe_execute().

    Raises:
        anthropic.APIError: on API-level failures.
    """
    system_text = _SYSTEM_PREFIX.format(
        schema_description=_schema_description(schema, dataframes)
    )

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=256,
        system=[
            {
                "type": "text",
                "text": system_text,
                # Cache the system prompt — schema is stable across questions
                # in a single session, so subsequent calls hit the cache.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": question}],
    )

    code = response.content[0].text.strip()

    # Strip accidental markdown code fences the model may emit
    if code.startswith("```"):
        lines = code.splitlines()
        # Drop opening fence (and optional language tag) and closing fence
        inner = [l for l in lines[1:] if not l.strip().startswith("```")]
        code = "\n".join(inner).strip()

    return code
