from datetime import datetime, date

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials


# =========================
# CONFIG
# =========================

st.set_page_config(
    page_title="AI Gearbox Selection Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SHEET_ID = "1RVD3MiEk_G8maxd20o99VKDf8ngNCv0I2AS00YPz_Fo"

REQUIRED_COLUMNS = [
    "lead_uid",
    "created_at",
    "logged_at",
    "source_channel",
    "request_text",
    "qualification_route",
    "identification_route",
    "rag_selection_status",
    "match_type",
    "selected_model",
    "selected_brand",
    "confidence",
    "missing_fields",
    "final_result",
    "process_status",
    "execution_time_sec",
    "error_message",
    "log_date",
]


# =========================
# STYLES
# =========================

def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(0, 255, 255, 0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(168, 85, 247, 0.16), transparent 30%),
                linear-gradient(135deg, #050816 0%, #070b1f 45%, #020617 100%);
            color: #E5E7EB;
        }

        [data-testid="stSidebar"] {
            background: rgba(5, 8, 22, 0.88);
            border-right: 1px solid rgba(0, 255, 255, 0.16);
        }

        .main-title {
            font-size: 2.35rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            background: linear-gradient(90deg, #22d3ee, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.15rem;
        }

        .subtitle {
            color: #94A3B8;
            font-size: 1rem;
            margin-bottom: 1.2rem;
        }

        .kpi-card {
            min-height: 135px;
            padding: 22px 20px;
            border-radius: 24px;
            background: linear-gradient(
                145deg,
                rgba(15, 23, 42, 0.92),
                rgba(17, 24, 39, 0.72)
            );
            border: 1px solid rgba(34, 211, 238, 0.24);
            box-shadow:
                0 0 24px rgba(34, 211, 238, 0.12),
                inset 0 0 32px rgba(168, 85, 247, 0.06);
        }

        .kpi-label {
            color: #94A3B8;
            font-size: 0.88rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }

        .kpi-value {
            color: #F8FAFC;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
        }

        .kpi-hint {
            color: #67E8F9;
            font-size: 0.85rem;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# GOOGLE SHEETS
# =========================

@st.cache_resource(show_spinner=False)
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    credentials_dict = dict(st.secrets["gcp_service_account"])

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        credentials_dict,
        scope,
    )

    return gspread.authorize(credentials)


@st.cache_data(ttl=60)
def load_sheet_data() -> pd.DataFrame:
    client = get_gspread_client()

    spreadsheet = client.open_by_key(SHEET_ID)

    worksheet = spreadsheet.sheet1

    records = worksheet.get_all_records()

    df = pd.DataFrame(records)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[REQUIRED_COLUMNS]


# =========================
# DATA PREP
# =========================

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["logged_at"] = pd.to_datetime(df["logged_at"], errors="coerce")
    df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce")

    df["event_datetime"] = (
        df["log_date"]
        .fillna(df["created_at"])
        .fillna(df["logged_at"])
    )

    df["event_datetime"] = pd.to_datetime(
        df["event_datetime"],
        errors="coerce"
    )

    df["event_date"] = df["event_datetime"].dt.floor("D")

    df["execution_time_sec"] = pd.to_numeric(
        df["execution_time_sec"],
        errors="coerce"
    ).fillna(0)

    text_columns = [
        "source_channel",
        "process_status",
        "match_type",
        "confidence",
        "error_message",
    ]

    for col in text_columns:
        df[col] = df[col].fillna("").astype(str)

    df["source_channel"] = df["source_channel"].replace("", "unknown")
    df["process_status"] = df["process_status"].replace("", "unknown")
    df["match_type"] = df["match_type"].replace("", "unknown")

    df["has_error"] = (
        df["error_message"].str.strip().ne("")
        |
        df["process_status"]
        .str.lower()
        .str.contains("error|failed|fail", regex=True, na=False)
    )

    return df


# =========================
# FILTERS
# =========================

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:

    st.sidebar.markdown("## Фильтры")

    min_date = df["event_date"].min().date()
    max_date = df["event_date"].max().date()

    period = st.sidebar.date_input(
        "Период",
        value=(min_date, max_date),
    )

    if len(period) == 2:
        start_date, end_date = period
    else:
        start_date = min_date
        end_date = max_date

    channels = st.sidebar.multiselect(
        "source_channel",
        sorted(df["source_channel"].unique()),
        default=sorted(df["source_channel"].unique())
    )

    statuses = st.sidebar.multiselect(
        "process_status",
        sorted(df["process_status"].unique()),
        default=sorted(df["process_status"].unique())
    )

    match_types = st.sidebar.multiselect(
        "match_type",
        sorted(df["match_type"].unique()),
        default=sorted(df["match_type"].unique())
    )

    filtered = df[
        (df["event_date"].dt.date >= start_date)
        &
        (df["event_date"].dt.date <= end_date)
        &
        (df["source_channel"].isin(channels))
        &
        (df["process_status"].isin(statuses))
        &
        (df["match_type"].isin(match_types))
    ]

    return filtered


# =========================
# HELPERS
# =========================

def update_plot_layout(fig):

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig


def kpi_card(label, value, hint=""):

    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# HEADER
# =========================

def render_header():

    st.markdown(
        """
        <div class="main-title">
            Мониторинг AI-системы
        </div>

        <div class="subtitle">
            Мониторинг системы по подбору редукторов:
            заявки, ошибки, стабильность, совпадения
            и операционные статусы.
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# KPIs
# =========================

def render_kpis(df):

    total_requests = len(df)

    avg_time = df["execution_time_sec"].mean()

    system_errors = int(df["has_error"].sum())

    exact_matches = int(
        df["match_type"]
        .str.lower()
        .isin(["exact", "exact_match"])
        .sum()
    )

    analog_matches = int(
        df["match_type"]
        .str.lower()
        .str.contains("analog|analogue", regex=True, na=False)
        .sum()
    )

    cols = st.columns(5)

    with cols[0]:
        kpi_card("ВСЕГО ЗАЯВОК", total_requests)

    with cols[1]:
        kpi_card(
            "СРЕДНЕЕ ВРЕМЯ",
            f"{avg_time:.2f} сек"
        )

    with cols[2]:
        kpi_card("ОШИБКИ СИСТЕМЫ", system_errors)

    with cols[3]:
        kpi_card("ТОЧНЫЕ СОВПАДЕНИЯ", exact_matches)

    with cols[4]:
        kpi_card("НАЙДЕННЫЕ АНАЛОГИ", analog_matches)


# =========================
# CHARTS
# =========================

def render_charts(df):

    daily = (
        df.dropna(subset=["event_date"])
        .groupby("event_date")
        .agg(
            requests=("lead_uid", "count"),
            errors=("has_error", "sum"),
        )
        .reset_index()
    )

    daily["event_date"] = pd.to_datetime(daily["event_date"])

    left, right = st.columns(2)

    with left:

        fig = px.area(
            daily,
            x="event_date",
            y="requests",
            title="Заявки по дням",
            markers=True,
        )

        st.plotly_chart(
            update_plot_layout(fig),
            use_container_width=True
        )

    with right:

        fig = px.bar(
            daily,
            x="event_date",
            y="errors",
            title="Ошибки по дням",
        )

        st.plotly_chart(
            update_plot_layout(fig),
            use_container_width=True
        )

    left, right = st.columns(2)

    with left:

        confidence_counts = (
            df["confidence"]
            .value_counts()
            .reset_index()
        )

        confidence_counts.columns = [
            "confidence",
            "count"
        ]

        fig = px.bar(
            confidence_counts,
            x="confidence",
            y="count",
            title="Распределение confidence",
        )

        st.plotly_chart(
            update_plot_layout(fig),
            use_container_width=True
        )

    with right:

        match_counts = (
            df["match_type"]
            .value_counts()
            .reset_index()
        )

        match_counts.columns = [
            "match_type",
            "count"
        ]

        fig = px.pie(
            match_counts,
            names="match_type",
            values="count",
            hole=0.55,
            title="Типы совпадений",
        )

        st.plotly_chart(
            update_plot_layout(fig),
            use_container_width=True
        )


# =========================
# TABLES
# =========================

def render_tables(df):

    st.markdown("## Операционные таблицы")

    st.dataframe(
        df.sort_values(
            "created_at",
            ascending=False
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================
# DOWNLOAD
# =========================

def render_download(df):

    csv = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="Скачать данные CSV",
        data=csv,
        file_name="dashboard_export.csv",
        mime="text/csv",
        use_container_width=True,
    )


# =========================
# AUTO REFRESH
# =========================

def auto_refresh_control():

    st.sidebar.markdown("## Auto refresh")

    enabled = st.sidebar.toggle(
        "Включить автообновление",
        value=False
    )

    interval = st.sidebar.number_input(
        "Интервал, секунд",
        min_value=10,
        max_value=3600,
        value=60,
        step=10,
    )

    if enabled:

        st.components.v1.html(
            f"""
            <script>
                setTimeout(function() {{
                    window.parent.location.reload();
                }}, {interval * 1000});
            </script>
            """,
            height=0,
        )

    st.sidebar.caption(
        f"Последнее обновление: "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


# =========================
# MAIN
# =========================

def main():

    inject_css()

    render_header()

    auto_refresh_control()

    try:

        raw_df = load_sheet_data()

    except Exception as exc:

        st.error(
            "Не удалось загрузить данные из Google Sheets."
        )

        st.exception(exc)

        st.stop()

    df = prepare_data(raw_df)

    if df.empty:

        st.warning(
            "Google Sheet загружен, но в нем нет данных."
        )

        st.stop()

    filtered_df = apply_filters(df)

    render_download(filtered_df)

    if filtered_df.empty:

        st.warning(
            "Нет данных по выбранным фильтрам."
        )

        st.stop()

    render_kpis(filtered_df)

    st.markdown("<br/>", unsafe_allow_html=True)

    render_charts(filtered_df)

    render_tables(filtered_df)


if __name__ == "__main__":
    main()
