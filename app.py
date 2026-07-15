"""
FMCG M&A Newsletter Agent — Streamlit Application

Three-tab interface:
1. Pipeline Run — execute the full pipeline and see funnel metrics
2. Newsletter Preview — read & download the generated newsletter
3. Raw Data Explorer — browse all pipeline data with filters
"""

import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FMCG M&A Newsletter Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }

    div[data-testid="stMetric"] label {
        color: #94a3b8;
        font-size: 0.85rem;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #e2e8f0;
        font-size: 1.8rem;
        font-weight: 700;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 2px solid #1e293b;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        color: #94a3b8;
    }

    .stTabs [aria-selected="true"] {
        color: #3b82f6;
        border-bottom: 3px solid #3b82f6;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.2s;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }

    /* Dataframe */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Headers */
    h1 {
        color: #f1f5f9;
        font-weight: 800;
    }

    h2, h3 {
        color: #e2e8f0;
    }

    /* Status badges */
    .status-kept { color: #22c55e; font-weight: 600; }
    .status-duplicate { color: #f59e0b; font-weight: 600; }
    .status-irrelevant { color: #ef4444; font-weight: 600; }
    .status-low-confidence { color: #f97316; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏭 FMCG M&A Agent")
    st.markdown("---")
    st.markdown(
        "**Pipeline:** Ingestion → Dedup → Scoring → Newsletter\n\n"
        "Sources: NewsAPI, GDELT, RSS feeds\n\n"
        "Dedup: Exact URL → Fuzzy title → Semantic embedding\n\n"
        "Relevance: Keyword pre-filter + LLM classification"
    )
    st.markdown("---")
    st.markdown("##### Configuration")

    # API key status indicators — try st.secrets for Streamlit Cloud, fall back to env vars
    newsapi_key = os.getenv("NEWSAPI_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    try:
        newsapi_key = newsapi_key or st.secrets.get("NEWSAPI_KEY", "")
        groq_key = groq_key or st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        pass  # No secrets.toml — running locally with .env

    if newsapi_key:
        os.environ["NEWSAPI_KEY"] = newsapi_key
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    st.markdown(f"NewsAPI: {'✅ Connected' if newsapi_key else '❌ Not set'}")
    st.markdown(f"Groq LLM: {'✅ Connected' if groq_key else '⚠️ Fallback mode'}")

    st.markdown("---")
    st.markdown(
        "Built for [Benori Knowledge Solutions](https://www.benoriknowledge.com/) "
        "FMCG M&A Intelligence Assignment"
    )


# ─── Main Content ───────────────────────────────────────────────────────────
st.markdown("# 📊 FMCG M&A Newsletter Agent")
st.markdown("*Automated FMCG deal intelligence — from raw news to boardroom-ready newsletter*")

tab1, tab2, tab3 = st.tabs(["🔄 Pipeline Run", "📰 Newsletter Preview", "📁 Raw Data Explorer"])


# ─── Tab 1: Pipeline Run ────────────────────────────────────────────────────
with tab1:
    st.markdown("### Run the Intelligence Pipeline")
    st.markdown(
        "Click below to execute the full pipeline: "
        "**Ingestion → De-duplication → Credibility Scoring → Relevance Filtering → "
        "Summarization → Newsletter Generation**"
    )

    col_btn, col_status = st.columns([1, 3])

    with col_btn:
        run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

    if run_clicked:
        with st.spinner("Running pipeline... This may take 1-2 minutes."):
            try:
                from pipeline import run_pipeline
                result = run_pipeline()
                st.session_state["pipeline_result"] = result
                st.session_state["last_run"] = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                st.session_state["pipeline_result"] = None

    if "pipeline_result" in st.session_state and st.session_state["pipeline_result"]:
        result = st.session_state["pipeline_result"]
        stats = result["stats"]

        st.markdown("---")
        st.markdown("### Pipeline Results")

        # Funnel metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📥 Raw Articles", stats.get("total_raw", 0))
        with col2:
            st.metric(
                "🔍 After Dedup",
                stats.get("after_dedup", 0),
                delta=f"-{stats.get('duplicates_removed', 0)} duplicates",
            )
        with col3:
            st.metric(
                "✅ Relevant Deals",
                stats.get("after_relevance", 0),
                delta=f"-{stats.get('irrelevant', 0)} irrelevant",
            )
        with col4:
            st.metric("📰 Newsletter Deals", stats.get("final_kept", 0))

        # Source breakdown
        st.markdown("#### Source Breakdown")
        src_col1, src_col2, src_col3 = st.columns(3)
        with src_col1:
            st.metric("NewsAPI", stats.get("newsapi_raw", 0))
        with src_col2:
            st.metric("GDELT", stats.get("gdelt_raw", 0))
        with src_col3:
            st.metric("RSS Feeds", stats.get("rss_raw", 0))

        # Funnel chart
        st.markdown("#### Pipeline Funnel")
        funnel_data = {
            "Stage": ["Raw Ingested", "After Dedup", "After Relevance", "Final (Kept)"],
            "Count": [
                stats.get("total_raw", 0),
                stats.get("after_dedup", 0),
                stats.get("after_relevance", 0),
                stats.get("final_kept", 0),
            ],
        }

        fig = go.Figure(go.Funnel(
            y=funnel_data["Stage"],
            x=funnel_data["Count"],
            textposition="inside",
            textinfo="value+percent initial",
            marker=dict(
                color=["#3b82f6", "#06b6d4", "#10b981", "#22c55e"],
                line=dict(width=1, color="#1e293b"),
            ),
            connector=dict(line=dict(color="#334155", width=1)),
        ))
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e2e8f0", size=14),
            height=350,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Last run timestamp
        if "last_run" in st.session_state:
            st.caption(f"Last run: {st.session_state['last_run']}")

    else:
        st.info("Click **Run Pipeline** to start. First run may take longer while models download.")


# ─── Tab 2: Newsletter Preview ──────────────────────────────────────────────
with tab2:
    if "pipeline_result" in st.session_state and st.session_state["pipeline_result"]:
        result = st.session_state["pipeline_result"]

        st.markdown("### 📰 Generated Newsletter")
        st.markdown("---")

        # Render the markdown newsletter
        st.markdown(result["newsletter_md"])

        st.markdown("---")

        # Download buttons
        st.markdown("### 📥 Download Newsletter")
        dl_col1, dl_col2 = st.columns(2)

        with dl_col1:
            # Download as markdown
            st.download_button(
                label="📄 Download Markdown",
                data=result["newsletter_md"],
                file_name="fmcg_newsletter.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with dl_col2:
            # Download as Word doc
            docx_path = result.get("newsletter_docx_path")
            if docx_path and os.path.exists(docx_path):
                with open(docx_path, "rb") as f:
                    st.download_button(
                        label="📝 Download Word (.docx)",
                        data=f.read(),
                        file_name="fmcg_newsletter.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )
            else:
                st.warning("Word document not available. Run the pipeline first.")
    else:
        st.info("Run the pipeline first to generate a newsletter.")


# ─── Tab 3: Raw Data Explorer ───────────────────────────────────────────────
with tab3:
    if "pipeline_result" in st.session_state and st.session_state["pipeline_result"]:
        result = st.session_state["pipeline_result"]
        articles = result["articles"]

        if articles:
            df = pd.DataFrame(articles)

            st.markdown("### 📁 Pipeline Data Explorer")
            st.markdown(
                f"Showing all **{len(df)}** articles processed through the pipeline, "
                "including those marked as duplicates or irrelevant."
            )

            # Filters
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                status_filter = st.multiselect(
                    "Filter by Pipeline Status",
                    options=df["pipeline_status"].dropna().unique().tolist(),
                    default=df["pipeline_status"].dropna().unique().tolist(),
                )
            with filter_col2:
                source_filter = st.multiselect(
                    "Filter by Source API",
                    options=df["source_api"].unique().tolist(),
                    default=df["source_api"].unique().tolist(),
                )

            filtered_df = df[
                df["pipeline_status"].isin(status_filter) &
                df["source_api"].isin(source_filter)
            ]

            st.markdown(f"**Showing {len(filtered_df)} of {len(df)} articles**")

            # Display columns (subset for readability)
            display_cols = [
                "title", "source_domain", "source_api", "pipeline_status",
                "deal_type", "credibility_tier", "relevance_confidence",
                "published_at",
            ]
            available_cols = [c for c in display_cols if c in filtered_df.columns]

            st.dataframe(
                filtered_df[available_cols],
                use_container_width=True,
                height=500,
            )

            # Download buttons
            st.markdown("### 📥 Download Raw Data")
            dl_col1, dl_col2 = st.columns(2)

            with dl_col1:
                csv_data = df.to_csv(index=False)
                st.download_button(
                    label="📊 Download CSV",
                    data=csv_data,
                    file_name="pipeline_output.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            with dl_col2:
                # Convert list columns for JSON serialization
                json_data = json.dumps(articles, indent=2, ensure_ascii=False, default=str)
                st.download_button(
                    label="📋 Download JSON",
                    data=json_data,
                    file_name="pipeline_output.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # Pipeline status distribution
            st.markdown("#### Status Distribution")
            status_counts = df["pipeline_status"].value_counts()
            fig_status = go.Figure(go.Pie(
                labels=status_counts.index.tolist(),
                values=status_counts.values.tolist(),
                marker=dict(colors=["#22c55e", "#f59e0b", "#ef4444", "#f97316"]),
                hole=0.4,
                textinfo="label+percent",
                textfont=dict(color="#e2e8f0"),
            ))
            fig_status.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=True,
                legend=dict(font=dict(color="#e2e8f0")),
            )
            st.plotly_chart(fig_status, use_container_width=True)

        else:
            st.warning("No articles in pipeline output.")
    else:
        st.info("Run the pipeline first to explore the raw data.")
