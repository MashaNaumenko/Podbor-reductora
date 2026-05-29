from datetime import datetime, date
from pathlib import Path
import base64

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from oauth2client.service_account import ServiceAccountCredentials


st.set_page_config(
    page_title="Мониторинг AI-системы",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

SHEET_ID = "1RVD3MiEk_G8maxd20o99VKDf8ngNCv0I2AS00YPz_Fo"

REQUIRED_COLUMNS = [
    "lead_uid", "created_at", "logged_at", "source_channel", "request_text",
    "qualification_route", "identification_route", "rag_selection_status",
    "match_type", "selected_model", "selected_brand", "confidence",
    "missing_fields", "final_result", "process_status",
    "execution_time_sec", "error_message", "log_date",
]


def image_to_base64(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return base64.b64encode(file_path.read_bytes()).decode()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 10% 10%, rgba(139,92,246,.14), transparent 28%),
                radial-gradient(circle at 85% 15%, rgba(249,115,22,.12), transparent 30%),
                linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            color: #0f172a;
        }

        [data-testid="stSidebar"] {
            background: rgba(255,255,255,.96);
            border-right: 1px solid #e2e8f0;
            box-shadow: 0 10px 30px rgba(15, 23, 42, .08);
        }
        /* Поле interval */

        .stNumberInput input {
            background: rgba(248,250,252,.92) !important;
            color: #0f172a !important;
            border: 1px solid #e2e8f0 !important;
        }

        .stNumberInput div[data-baseweb="input"] {
            background: rgba(248,250,252,.92) !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
        }

/* Кнопки + / - */

.stNumberInput button {
    background: rgba(248,250,252,.92) !important;
    color: #0f172a !important;
    border: 1px solid #e2e8f0 !important;
}
        /* Светлые select-box / multiselect */

        .stMultiSelect div[data-baseweb="select"] > div {
            background: rgba(248,250,252,.92) !important;
            border: 1px solid #e2e8f0 !important;
        }

        .stSelectbox div[data-baseweb="select"] > div {
            background: rgba(248,250,252,.92) !important;
            border: 1px solid #e2e8f0 !important;
        }

        .stDateInput > div > div {
            background: rgba(248,250,252,.92) !important;
            border: 1px solid #e2e8f0 !important;
        }

/* Цвет текста */

        .stMultiSelect span,
        .stSelectbox span,
        .stDateInput input {
            color: #0f172a !important;
        }

/* Ось X и Y графиков */

        .js-plotly-plot .plotly .xtick text,
        .js-plotly-plot .plotly .ytick text {
            fill: #0f172a !important;
            color: #0f172a !important;
            font-weight: 700 !important;
        }

        [data-testid="stSidebar"] * {
            color: #0f172a;
        }

        .main-header {
            background: rgba(255,255,255,.88);
            border: 1px solid #e2e8f0;
            border-radius: 30px;
            padding: 28px 34px;
            box-shadow: 0 22px 60px rgba(15,23,42,.10);
            margin-bottom: 26px;
        }

        .header-grid {
            display: grid;
            grid-template-columns: 220px 1fr;
            gap: 28px;
            align-items: center;
        }

        .logo-box img {
            max-width: 210px;
            height: auto;
        }

        .main-title {
            font-size: 3rem;
            font-weight: 950;
            letter-spacing: -0.055em;
            line-height: 1;
            background: linear-gradient(100deg, #8b5cf6, #ec4899, #f97316);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }

        .subtitle {
            color: #475569;
            font-size: 1.05rem;
            line-height: 1.55;
            max-width: 900px;
        }

        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 18px;
        }

        .badge {
            padding: 9px 14px;
            border-radius: 999px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            color: #334155;
            font-weight: 800;
            font-size: .82rem;
        }

        .badge.hot {
            color: white;
            border: none;
            background: linear-gradient(100deg, #8b5cf6, #ec4899, #f97316);
            box-shadow: 0 12px 28px rgba(236,72,153,.20);
        }

        .kpi-card {
            min-height: 145px;
            padding: 24px 22px;
            border-radius: 28px;
            background: rgba(255,255,255,.88);
            border: 1px solid #e2e8f0;
            box-shadow: 0 14px 34px rgba(15,23,42,.09);
            position: relative;
            overflow: hidden;
        }

        .kpi-card:before {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 15% 0%, rgba(139,92,246,.14), transparent 36%);
        }

        .kpi-label {
            position: relative;
            color: #64748b;
            font-size: .78rem;
            text-transform: uppercase;
            letter-spacing: .12em;
            font-weight: 950;
            margin-bottom: 12px;
        }

        .kpi-value {
            position: relative;
            color: #0f172a;
            font-size: 2.2rem;
            font-weight: 950;
            line-height: 1.1;
        }

        .kpi-hint {
            position: relative;
            color: #7c3aed;
            font-size: .88rem;
            margin-top: 10px;
            font-weight: 700;
        }

        .section-title {
            font-size: 1.8rem;
            font-weight: 950;
            color: #0f172a;
            margin: 32px 0 18px;
        }

        .stDownloadButton > button {
            border-radius: 18px !important;
            border: 1px solid #e2e8f0 !important;
            background: linear-gradient(100deg, #8b5cf6, #ec4899, #f97316) !important;
            color: white !important;
            font-weight: 900 !important;
            padding: 14px 18px !important;
            box-shadow: 0 14px 35px rgba(236,72,153,.18) !important;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 24px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
            box-shadow: 0 14px 34px rgba(15,23,42,.08);
        }

        .stMultiSelect [data-baseweb="tag"] {
            background: linear-gradient(100deg, #8b5cf6, #ec4899, #f97316) !important;
            color: white !important;
            border-radius: 999px !important;
        }

        @media(max-width: 900px) {
            .header-grid {
                grid-template-columns: 1fr;
            }
            .main-title {
                font-size: 2.2rem;
            }
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
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)

    return gspread.authorize(credentials)


@st.cache_data(ttl=60)
def load_sheet_data() -> pd.DataFrame:
    client = get_gspread_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet("Лист 1")

    records = worksheet.get_all_records()
    df = pd.DataFrame(records)

    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None

    return df[REQUIRED_COLUMNS]


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

    df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
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
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["source_channel"] = df["source_channel"].replace({
        "": "Не определено",
        "chat": "Чат",
        "email": "Email",
        "system_error": "Системная ошибка",
        "unknown": "Не определено",
    })

    df["process_status"] = df["process_status"].replace({
        "": "Не определено",
        "error": "Ошибка",
        "reply_received_waiting_update": "Получен ответ клиента",
        "reply_received_but_more_data_needed": "Ответ получен, данных мало",
        "selection_result_ready_for_chat": "Подбор готов",
        "selection_result_ready_for_email": "Подбор готов",
        "waiting_for_identification_clarification": "Ожидание уточнений",
        "unknown": "Не определено",
    })

    df["match_type"] = df["match_type"].replace({
        "": "Не определено",
        "analogue": "Аналог",
        "analog": "Аналог",
        "exact": "Точное совпадение",
        "exact_match": "Точное совпадение",
        "unknown": "Не определено",
    })

    df["has_error"] = (
        df["error_message"].str.strip().ne("")
        |
        df["process_status"].str.lower().str.contains("ошибка|error|failed|fail", regex=True, na=False)
    )

    return df


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("## Фильтры")

    valid_dates = df["event_date"].dropna()

    if valid_dates.empty:
        min_date = max_date = date.today()
    else:
        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()

    period = st.sidebar.date_input(
        "Период",
        value=(min_date, max_date),
    )

    if isinstance(period, tuple) and len(period) == 2:
        start_date, end_date = period
    else:
        start_date, end_date = min_date, max_date

    channels = st.sidebar.multiselect(
        "Канал заявки",
        sorted(df["source_channel"].dropna().unique()),
        default=sorted(df["source_channel"].dropna().unique()),
    )

    statuses = st.sidebar.multiselect(
        "Статус процесса",
        sorted(df["process_status"].dropna().unique()),
        default=sorted(df["process_status"].dropna().unique()),
    )

    match_types = st.sidebar.multiselect(
        "Тип результата",
        sorted(df["match_type"].dropna().unique()),
        default=sorted(df["match_type"].dropna().unique()),
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


def update_plot_layout(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.55)",
        font=dict(color="#000000", size=14),
        margin=dict(l=20, r=20, t=56, b=20),
        title=dict(font=dict(size=20, color="#0f172a")),
        legend=dict(
            bgcolor="rgba(255,255,255,0)",
            font=dict(color="#334155"),
        ),
    )
    fig.update_xaxes(
        tickfont=dict(color="#000000", size=13),
        title_font=dict(color="#000000"),
    )

    fig.update_yaxes(
        tickfont=dict(color="#000000", size=13),
        title_font=dict(color="#000000"),
    )
    fig.update_xaxes(
        tickformat="%d.%m.%Y",
        showgrid=True,
        gridcolor="rgba(148,163,184,.22)",
        color="#475569",
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,.22)",
        color="#475569",
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


def render_header():
    logo_base64 = image_to_base64("logo.png")

    if logo_base64:
        logo_html = f'<div class="logo-box"><img src="data:image/png;base64,{logo_base64}" /></div>'
    else:
        logo_html = '<div class="logo-box"><div class="badge hot">Промышленные редукторы</div></div>'

    st.markdown(
        f"""
        <div class="main-header">
            <div class="header-grid">
                {logo_html}
                <div>
                    <div class="main-title">Мониторинг AI-системы</div>
                    <div class="subtitle">
                        Панель управления AI-агентом по подбору редукторов:
                        заявки, ошибки, стабильность workflow, совпадения,
                        скорость обработки и операционные статусы.
                    </div>
                    <div class="badge-row">
                        <div class="badge hot">AI-агент</div>
                        <div class="badge">n8n</div>
                        <div class="badge">RAG</div>
                        <div class="badge">Google Sheets</div>
                        <div class="badge">Telegram Monitoring</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(df):
    total_requests = len(df)
    avg_time = df["execution_time_sec"].mean()
    system_errors = int(df["has_error"].sum())

    exact_matches = int(
        df["match_type"]
        .str.lower()
        .isin(["точное совпадение"])
        .sum()
    )

    analog_matches = int(
        df["match_type"]
        .str.lower()
        .str.contains("аналог", regex=True, na=False)
        .sum()
    )

    cols = st.columns(5)

    with cols[0]:
        kpi_card("ВСЕГО ЗАЯВОК", total_requests, "обработанные события")

    with cols[1]:
        kpi_card("СРЕДНЕЕ ВРЕМЯ", f"{avg_time:.2f} сек", "скорость обработки")

    with cols[2]:
        kpi_card("ОШИБКИ СИСТЕМЫ", system_errors, "контроль стабильности")

    with cols[3]:
        kpi_card("ТОЧНЫЕ СОВПАДЕНИЯ", exact_matches, "результат подбора")

    with cols[4]:
        kpi_card("НАЙДЕННЫЕ АНАЛОГИ", analog_matches, "альтернативные модели")


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
            color_discrete_sequence=["#8b5cf6"],
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    with right:
        fig = px.bar(
            daily,
            x="event_date",
            y="errors",
            title="Ошибки по дням",
            color_discrete_sequence=["#ef4444"],
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)

    left, right = st.columns(2)

    with left:
        confidence_counts = df["confidence"].replace("", "Не указано").value_counts().reset_index()
        confidence_counts.columns = ["confidence", "count"]

        fig = px.bar(
            confidence_counts,
            x="confidence",
            y="count",
            title="Распределение confidence",
            color_discrete_sequence=["#ec4899"],
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
            color_discrete_sequence=["#8b5cf6", "#ec4899", "#f97316", "#22c55e", "#06b6d4"],
        )
        st.plotly_chart(update_plot_layout(fig), use_container_width=True)


def render_tables(df):
    st.markdown('<div class="section-title">Операционные таблицы</div>', unsafe_allow_html=True)

    st.dataframe(
        df.sort_values("created_at", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


def render_download(df):
    csv = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="Скачать данные CSV",
        data=csv,
        file_name="dashboard_export.csv",
        mime="text/csv",
        use_container_width=True,
    )


def auto_refresh_control():
    st.sidebar.markdown("## Auto refresh")

    enabled = st.sidebar.toggle(
        "Включить автообновление",
        value=False,
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
        f"Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def main():
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
