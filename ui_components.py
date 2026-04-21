from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
<style>
/* Layout tweaks */
.block-container { padding-top: 1.4rem; padding-bottom: 2.2rem; }

/* KPI cards */
.ka-kpi {
  border-radius: 14px;
  padding: 14px 14px 12px 14px;
  border: 1px solid rgba(17,24,39,0.08);
  background: white;
  box-shadow: 0 1px 1px rgba(0,0,0,0.02);
}
.ka-kpi .label { font-size: 0.82rem; color: rgba(17,24,39,0.7); margin-bottom: 6px; }
.ka-kpi .value { font-size: 1.25rem; font-weight: 700; color: rgba(17,24,39,0.96); line-height: 1.2; }
.ka-kpi .sub { font-size: 0.78rem; color: rgba(17,24,39,0.60); margin-top: 6px; }
.ka-dot { display:inline-block; width:10px; height:10px; border-radius:999px; margin-right:8px; transform: translateY(1px); }

/* Insight box */
.ka-insight {
  border-radius: 14px;
  padding: 14px;
  border: 1px solid rgba(17,24,39,0.08);
  background: linear-gradient(180deg, rgba(37,99,235,0.06), rgba(37,99,235,0.02));
}
.ka-insight ul { margin: 0.4rem 0 0 1.1rem; }
.ka-insight li { margin: 0.18rem 0; }

/* Small helper text */
.ka-muted { color: rgba(17,24,39,0.6); font-size: 0.86rem; }
</style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, color: str, sub: str | None = None) -> None:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
<div class="ka-kpi">
  <div class="label"><span class="ka-dot" style="background:{color};"></span>{label}</div>
  <div class="value">{value}</div>
  {sub_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def insight_box(title: str, bullets: list[str]) -> None:
    items = "".join(f"<li>{b}</li>" for b in bullets) if bullets else "<li>Chưa có insight.</li>"
    st.markdown(
        f"""
<div class="ka-insight">
  <div style="font-weight:700; margin-bottom:6px;">{title}</div>
  <ul>{items}</ul>
</div>
        """,
        unsafe_allow_html=True,
    )


def info_line(text: str) -> None:
    st.markdown(f'<div class="ka-muted">{text}</div>', unsafe_allow_html=True)

