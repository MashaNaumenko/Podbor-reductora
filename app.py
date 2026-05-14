import time
from datetime import datetime, date

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials


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
            position: relative;
            overflow: hidden;
            min-height: 135px;
            padding: 22px 20px;
            border-radius: 24px;
            background: linear-gradient(145deg, rgba(15, 23, 42, 0.92), rgba(17, 24, 39, 0.72));
            border: 1px solid rgba(34, 211, 238, 0.24);
            box-shadow:
                0 0 24px rgba(34, 211, 238, 0.12),
                inset 0 0 32px rgba(168, 85, 247, 0.06);
            animation: pulseGlow 4s ease-in-out infinite;
        }

        .kpi-content {
            position: relative;
            z-index: 2;
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

        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 22px rgba(34, 211, 238, 0.10); }
            50% { box-shadow: 0 0 34px rgba(168, 85, 247, 0.20); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


@st.cache_data(ttl=60, show_spinner="Загружаю данные из Google Sheets...")
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


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Даты
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df["logged_at"] = pd.to_datetime(df["logged_at"], errors="coerce")
    df["log_date"] = pd.to_datetime(df["log_date"], errors="coerce")

    # Если log_date пустой, берем дату из created_at
    df["event_datetime"] = df["log_date"].fillna(df["created_at"]).fillna(df["logged_at"])
    df["event_date"] = df["event_datetime"].dt.date

    # Числа
    df["execution_time_sec"] = pd.to_numeric(df["execution_time_sec"], errors="coerce").fillna(0)

    # Текстовые поля
    text_cols = [
        "lead_uid",
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
        "error_message",
    ]

    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["source_channel"] = df["source_channel"].replace("", "unknown")
    df["process_status"] = df["process_status"].replace("", "unknown")
    df["match_type"] = df["match_type"].replace("", "unknown")
    df["confidence"] = df["confidence"].replace("", "unknown")

    df["has_error"] = (
        df["error_message"].str.strip().ne("")
        | df["process_status"].str.lower().str.contains("error|failed|fail", regex=True, na=False)
    )

    return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("## Фильтры")

    valid_dates = df["event_date"].dropna()

    if valid_dates.empty:
        min_date = max_date = date.today()
    else:
        min_date = valid_dates.min()
        max_date = valid_dates.max()

    period = st.sidebar.date_input(
        "Период",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(period, tuple) and len(period) == 2:
        start_date, end_date = period
    else:
        start_date, end_date = min_date, max_date

    channels_all = sorted(df["source_channel"].dropna().unique())
    statuses_all = sorted(df["process_status"].dropna().unique())
    match_types_all = sorted(df["match_type"].dropna().unique())
    confidence_all = sorted(df["confidence"].dropna().unique())

    channels = st.sidebar.multiselect(
        "source_channel",
        channels_all,
        default=channels_all,
    )

    statuses = st.sidebar.multiselect(
        "process_status",
        statuses_all,
        default=statuses_all,
    )

    match_types = st.sidebar.multiselect(
        "match_type",
        match_types_all,
        default=match_types_all,
    )

    confidence_values = st.sidebar.multiselect(
        "confidence",
        confidence_all,
        default=confidence_all,
    )

    filtered = df[
        (df["event_date"] >= start_date)
        & (df["event_date"] <= end_date)
        & (df["source_channel"].isin(channels))
        & (df["process_status"].isin(statuses))
        & (df["match_type"].isin(match_types))
        & (df["confidence"].isin(confidence_values))
    ]

    return filtered


def update_plot_layout(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(2,6,23,0.45)",
        font=dict(color="#E5E7EB"),
        margin=dict(l=20, r=20, t=55, b=20),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    return fig


def kpi_card(label: str, value: str, hint: str = "") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-content">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-hint">{hint}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_seconds(value: float) -> str:
    if pd.isna(value):
        return "0.00 сек"
    return f"{value:.2f} сек"


def render_header() -> None:
    st.markdown(
        """
        <div class="main-title">AI Gearbox Selection Dashboard</div>
        <div class="subtitle">
            Мониторинг AI-системы подбора редукторов: заявки, ошибки, confidence, совпадения и операционные статусы.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df: pd.DataFrame) -> None:
    total_requests = len(df)
    avg_time = df["execution_time_sec"].mean()
    system_errors = int(df["has_error"].sum())

    exact_matches = int(
        df["match_type"]
        .str.lower()
        .isin(["exact", "exact_match", "exact_match_found", "точное совпадение", "точный"])
        .sum()
    )

    analog_matches = int(
        df["match_type"]
        .str.lower()
        .str.contains("analog|analogue|анал", regex=True, na=False)
        .sum()
    )

    cols = st.columns(5)

    with cols[0]:
        kpi_card("Всего заявок", f"{total_requests}", "filtered leads")
    with cols[1]:
        kpi_card("Среднее время", format_seconds(avg_time), "processing latency")
    with cols[2]:
        kpi_card("Ошибки системы", str(system_errors), "error events")
    with cols[3]:
        kpi_card("Точные совпадения", str(exact_matches), "exact matches")
    with cols[4]:
        kpi_card("Найденные аналоги", str(analog_matches), "analog matches")


def render_charts(df: pd.DataFrame) -> None:
    left, right = st.columns(2)

    daily = (
        df.dropna(subset=["event_date"])
        .groupby("event_date", as_index=False)
        .agg(requests=("lead_uid", "count"), errors=("has_error", "sum"))
    )

    with left:
        fig = px.area(
            daily,
            x="event_date",
            y="requests",
            title="Заявки по дням",
            markers=True,
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    with right:
        fig = px.bar(
            daily,
            x="event_date",
            y="errors",
            title="Ошибки по дням",
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    left, right = st.columns(2)

    with left:
        confidence_counts = df["confidence"].value_counts().reset_index()
        confidence_counts.columns = ["confidence", "count"]

        fig = px.bar(
            confidence_counts,
            x="confidence",
            y="count",
            title="Распределение confidence",
            text_auto=True,
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    with right:
        match_counts = df["match_type"].value_counts().reset_index()
        match_counts.columns = ["match_type", "count"]

        fig = px.pie(
            match_counts,
            names="match_type",
            values="count",
            hole=0.55,
            title="Типы совпадений",
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    status_counts = df["process_status"].value_counts().reset_index()
    status_counts.columns = ["process_status", "count"]

    fig = px.bar(
        status_counts,
        x="process_status",
        y="count",
        title="process_status",
        text_auto=True,
    )
    st.plotly_chart(update_plot_layout(fig), use_container_width=True)


def render_tables(df: pd.DataFrame) -> None:
    st.markdown("## Операционные таблицы")

    latest_cols = [
        "lead_uid",
        "created_at",
        "source_channel",
        "request_text",
        "match_type",
        "selected_model",
        "selected_brand",
        "confidence",
        "process_status",
        "execution_time_sec",
    ]

    errors_cols = [
        "lead_uid",
        "created_at",
        "source_channel",
        "request_text",
        "process_status",
        "error_message",
        "execution_time_sec",
    ]

    problem_cols = [
        "lead_uid",
        "created_at",
        "source_channel",
        "request_text",
        "confidence",
        "missing_fields",
        "final_result",
        "process_status",
        "error_message",
    ]

    tab1, tab2, tab3 = st.tabs(
        ["Последние заявки", "Последние ошибки", "Проблемные заявки"]
    )

    with tab1:
        latest = df.sort_values("created_at", ascending=False).head(50)
        st.dataframe(latest[latest_cols], use_container_width=True, hide_index=True)

    with tab2:
        errors = df[df["has_error"]].sort_values("created_at", ascending=False).head(50)
        st.dataframe(errors[errors_cols], use_container_width=True, hide_index=True)

    with tab3:
        problematic = df[
            df["has_error"]
            | df["confidence"].str.lower().isin(["low", "низкая"])
            | df["missing_fields"].str.strip().ne("")
        ].sort_values("created_at", ascending=False).head(100)

        st.dataframe(problematic[problem_cols], use_container_width=True, hide_index=True)


def render_download(df: pd.DataFrame) -> None:
    csv = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="⬇️ Скачать отфильтрованные данные CSV",
        data=csv,
        file_name=f"gearbox_ai_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def auto_refresh_control() -> None:
    st.sidebar.markdown("## Auto refresh")

    enabled = st.sidebar.toggle("Включить автообновление", value=False)
    interval = st.sidebar.number_input(
        "Интервал, секунд",
        min_value=30,
        max_value=3600,
        value=60,
        step=30,
    )

    if enabled:
        st.components.v1.html(
            f"""
            <script>
                setTimeout(function() {{
                    window.parent.location.reload();
                }}, {int(interval) * 1000});
            </script>
            """,
            height=0,
        )

    st.sidebar.caption(
        f"Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def main() -> None:
    inject_css()
    render_header()
    auto_refresh_control()

    try:
        raw_df = load_sheet_data()
    except Exception as exc:
        st.error("Не удалось загрузить данные из Google Sheets.")
        st.exception(exc)
        st.stop()

    df = prepare_data(raw_df)

    if df.empty:
        st.warning("Google Sheet загружен, но в нем нет данных.")
        st.stop()

    filtered_df = apply_filters(df)

    render_download(filtered_df)

    if filtered_df.empty:
        st.warning("Нет данных по выбранным фильтрам.")
        st.stop()

    render_kpis(filtered_df)
    st.markdown("<br/>", unsafe_allow_html=True)
    render_charts(filtered_df)
    render_tables(filtered_df)


if __name__ == "__main__":
    main()
