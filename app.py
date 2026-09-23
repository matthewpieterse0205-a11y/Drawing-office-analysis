import streamlit as st
import pandas as pd
import plotly.express as px
from odoo_client import OdooClient
from metrics import normalize_jobs, apply_filters, overview_metrics, monthly_summary, draughtsman_summary, current_workload

st.set_page_config(page_title="Drawing Office Dashboard", page_icon="📐", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.2rem}
div[data-testid="stMetric"]{background:#15181d;border:1px solid #2b3138;padding:14px;border-radius:14px}
section[data-testid="stSidebar"]{border-right:1px solid #2b3138}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    try:
        c = OdooClient.from_streamlit_secrets(st.secrets)
        return normalize_jobs(c.fetch_drawing_office_jobs()), "Live Odoo", ""
    except Exception as e:
        return normalize_jobs(pd.read_csv("sample_jobs.csv")), "Sample data", str(e)

jobs, source, connection_error = load_data()


st.sidebar.markdown("## Drawing Office")
st.sidebar.caption("Data source: " + source)
if connection_error:
    st.sidebar.error("Odoo connection error: " + connection_error)
page = st.sidebar.radio("Navigate", ["Overview","Monthly Performance","Draughtsmen","Jobs","Drawing Output","Live Workload"])

st.sidebar.markdown("---")
st.sidebar.markdown("### Filters")
min_d = pd.to_datetime(jobs["created_at"]).min().date()
max_d = pd.to_datetime(jobs["created_at"]).max().date()
dr = st.sidebar.date_input("Date range", (min_d, max_d))
start_date, end_date = dr if isinstance(dr, tuple) and len(dr)==2 else (min_d, max_d)

people = sorted({p.strip() for s in jobs["assignees"].fillna("") for p in str(s).split("|") if p.strip()})
f_people = st.sidebar.multiselect("Draughtsman", people)
f_customer = st.sidebar.multiselect("Customer", sorted(jobs["customer"].dropna().astype(str).unique()))
f_type = st.sidebar.multiselect("Type", ["New","Release","Other"])
f_priority = st.sidebar.multiselect("Priority", sorted(jobs["priority"].dropna().astype(str).unique()))
f_stage = st.sidebar.multiselect("Stage", sorted(jobs["stage"].dropna().astype(str).unique()))
f_job = st.sidebar.text_input("Job number contains")

received_filtered = apply_filters(
    jobs,
    start_date,
    end_date,
    f_people,
    f_customer,
    f_type,
    f_priority,
    f_stage,
    f_job,
    date_field="created_at"
)

completed_filtered = apply_filters(
    jobs,
    start_date,
    end_date,
    f_people,
    f_customer,
    f_type,
    f_priority,
    f_stage,
    f_job,
    date_field="completed_at"
)

base_filtered = apply_filters(
    jobs,
    None,
    None,
    f_people,
    f_customer,
    f_type,
    f_priority,
    f_stage,
    f_job
)
st.title("Drawing Office Performance")
st.caption("V1 • New + Release = New • Shared credit = ceil(drawings ÷ assigned draughtsmen)")

if page == "Overview":
    received_m = overview_metrics(received_filtered)
    completed_m = overview_metrics(completed_filtered)
    base_m = overview_metrics(base_filtered)

    a,b,c,d = st.columns(4)
    a.metric("Jobs Received", received_m["jobs_received"])
    b.metric("Jobs Completed", completed_m["jobs_completed"])
    c.metric("Total Drawings", f'{received_m["total_drawings"]:.0f}')
    d.metric("Avg Drawings / Job", f'{received_m["avg_drawings_per_job"]:.1f}')

    a,b,c = st.columns(3)
    a.metric("Avg Turnaround", f'{completed_m["avg_turnaround_days"]:.1f} d')
    b.metric("Current Backlog", base_m["backlog_jobs"])
    c.metric("New Drawings", f'{received_m["new_drawings"]:.0f}')

    a,b = st.columns(2)
    a.metric("Release Drawings", f'{received_m["release_drawings"]:.0f}')
    ms = monthly_summary(base_filtered, start_date, end_date)
    l,r = st.columns(2)
    with l:
        st.plotly_chart(px.bar(ms, x="month", y=["jobs_received","jobs_completed"], barmode="group", title="Jobs received vs completed"), use_container_width=True)
    with r:
        st.plotly_chart(px.bar(ms, x="month", y=["new_drawings","release_drawings"], barmode="group", title="New vs release drawings"), use_container_width=True)
    l,r = st.columns(2)
    with l:
        st.plotly_chart(px.line(ms, x="month", y="avg_turnaround_days", markers=True, title="Average turnaround time"), use_container_width=True)
    with r:
        st.plotly_chart(px.line(ms, x="month", y="avg_drawings_per_job", markers=True, title="Average drawings per job"), use_container_width=True)

elif page == "Monthly Performance":
    ms = monthly_summary(base_filtered, start_date, end_date)
    st.dataframe(ms, use_container_width=True, hide_index=True)
    metric = st.selectbox("Trend metric", [c for c in ms.columns if c != "month"])
   

elif page == "Draughtsmen":
    ds = draughtsman_summary(base_filtered)
    st.caption("Shared drawings are split equally and each person's credit is rounded up.")
    st.dataframe(ds, use_container_width=True, hide_index=True)

elif page == "Jobs":
    cols = [
        "job_number",
        "customer",
        "job_type",
        "drawing_count",
        "credited_drawings_per_person",
        "assignees",
        "stage",
        "priority",
        "created_at",
        "completed_at",
        "turnaround_days",
        "waiting_days",
        "active_days",
        "repeat_count"
    ]

    st.dataframe(
        base_filtered[[c for c in cols if c in base_filtered.columns]],
        use_container_width=True,
        hide_index=True
    )

elif page == "Drawing Output":
    ms = monthly_summary(base_filtered, start_date, end_date)

    st.plotly_chart(
        px.bar(
            ms,
            x="month",
            y=["new_drawings", "release_drawings"],
            barmode="group",
            title="New vs Release Drawings"
        ),
        use_container_width=True
    )

    st.plotly_chart(
        px.line(
            ms,
            x="month",
            y="avg_drawings_per_job",
            markers=True,
            title="Average Drawings per Job"
        ),
        use_container_width=True
    )
elif page == "Live Workload":
    st.caption("Live Odoo mode refreshes every 60 seconds.")
    live = current_workload(jobs)
    st.dataframe(live, use_container_width=True, hide_index=True)