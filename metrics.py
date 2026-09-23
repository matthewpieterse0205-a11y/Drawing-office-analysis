import math
import pandas as pd
import numpy as np

RELEASE_VARIANTS = ["release","relaese","realese","releaste"]

def classify_job(x):
    s = str(x or "").lower()
    if "new" in s: return "New"
    if any(v in s for v in RELEASE_VARIANTS): return "Release"
    return "Other"

def normalize_jobs(df):
    df = df.copy()
    defaults = {"job_number":"","customer":"","requirements":"","drawing_count":np.nan,"assignees":"","stage":"","priority":"","description":"","created_at":pd.NaT,"completed_at":pd.NaT,"first_stage_change_at":pd.NaT,"deadline":pd.NaT}
    for k,v in defaults.items():
        if k not in df.columns: df[k]=v
    for c in ["created_at","completed_at","first_stage_change_at","deadline"]:
        df[c]=pd.to_datetime(df[c], errors="coerce")
    df["drawing_count"]=pd.to_numeric(df["drawing_count"], errors="coerce")
    df["job_type"]=df["requirements"].apply(classify_job)
    df["assignees"]=df["assignees"].fillna("").astype(str)
    df["assignee_count"]=df["assignees"].apply(lambda s:max(1,len([x for x in s.split("|") if x.strip()])))
    df["credited_drawings_per_person"]=df.apply(lambda r: math.ceil(r["drawing_count"]/r["assignee_count"]) if pd.notna(r["drawing_count"]) and r["drawing_count"]>0 else 0, axis=1)
    df["turnaround_days"]=(df["completed_at"]-df["created_at"]).dt.total_seconds()/86400
    df["waiting_days"]=(df["first_stage_change_at"]-df["created_at"]).dt.total_seconds()/86400
    df["active_days"]=(df["completed_at"]-df["first_stage_change_at"]).dt.total_seconds()/86400
    df["time_per_drawing_days"]=df.apply(lambda r:r["turnaround_days"]/r["drawing_count"] if pd.notna(r["turnaround_days"]) and pd.notna(r["drawing_count"]) and r["drawing_count"]>0 else np.nan, axis=1)
    df["repeat_count"]=df.groupby("job_number")["job_number"].transform("count").fillna(0).astype(int)
    return df

def apply_filters(
    df,
    start_date,
    end_date,
    people,
    customers,
    job_types,
    priorities,
    stages,
    job_search,
    date_field="created_at"
):
    x = df.copy()

    if start_date is not None and end_date is not None:
        x = x[
            (x[date_field].dt.date >= start_date) &
            (x[date_field].dt.date <= end_date)
        ].copy()

    if people:
        x = x[
            x["assignees"].apply(
                lambda s: any(
                    p in [q.strip() for q in str(s).split("|")]
                    for p in people
                )
            )
        ]

    if customers:
        x = x[x["customer"].isin(customers)]

    if job_types:
        x = x[x["job_type"].isin(job_types)]

    if priorities:
        x = x[x["priority"].isin(priorities)]

    if stages:
        x = x[x["stage"].isin(stages)]

    if job_search:
        x = x[
            x["job_number"]
            .astype(str)
            .str.contains(job_search, case=False, na=False)
        ]

    return x

def overview_metrics(df):
    comp=df[df["completed_at"].notna()]
    td=df["drawing_count"].fillna(0).sum()
    backlog=df[df["stage"].isin(["Not Started","In Progress","On Hold"])]
    return {
        "jobs_received":len(df),"jobs_completed":len(comp),"total_drawings":td,
        "avg_drawings_per_job":td/len(df) if len(df) else 0,
        "avg_turnaround_days":comp["turnaround_days"].mean() if len(comp) else 0,
        "avg_waiting_days":comp["waiting_days"].mean() if len(comp) else 0,
        "avg_active_days":comp["active_days"].mean() if len(comp) else 0,
        "avg_time_per_drawing_days":comp["time_per_drawing_days"].mean() if len(comp) else 0,
        "new_drawings":df.loc[df["job_type"]=="New","drawing_count"].fillna(0).sum(),
        "release_drawings":df.loc[df["job_type"]=="Release","drawing_count"].fillna(0).sum(),
        "backlog_jobs":len(backlog)
    }

def monthly_summary(df, start_date=None, end_date=None):
    columns = [
        "month",
        "jobs_received",
        "jobs_completed",
        "total_drawings",
        "new_drawings",
        "release_drawings",
        "avg_drawings_per_job",
        "avg_turnaround_days",
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    x = df.copy()

    # April must never appear as a reporting month
    report_start = pd.Timestamp("2026-05-01")

    # Use selected date range, but never display anything before May 2026
    if start_date is None:
        effective_start = report_start
    else:
        effective_start = max(
            pd.Timestamp(start_date),
            report_start
        )

    if end_date is None:
        effective_end = pd.Timestamp.today()
    else:
        effective_end = pd.Timestamp(end_date)

    # Create the reporting months from the selected range
    months = pd.period_range(
        effective_start,
        effective_end,
        freq="M"
    )

    rows = []

    for month in months:

        month_start = month.start_time
        month_end = month.end_time

        # RECEIVED uses created_at
        received = x[
            (x["created_at"] >= month_start) &
            (x["created_at"] <= month_end)
        ]

        # COMPLETED uses completed_at
        # This includes jobs created before the selected period
        completed = x[
            (x["completed_at"].notna()) &
            (x["completed_at"] >= month_start) &
            (x["completed_at"] <= month_end)
        ]

        total_drawings = received["drawing_count"].fillna(0).sum()

        rows.append({
            "month": month.strftime("%b %Y"),

            "jobs_received":
                len(received),

            "jobs_completed":
                len(completed),

            "total_drawings":
                total_drawings,

            "new_drawings":
                received.loc[
                    received["job_type"] == "New",
                    "drawing_count"
                ].fillna(0).sum(),

            "release_drawings":
                received.loc[
                    received["job_type"] == "Release",
                    "drawing_count"
                ].fillna(0).sum(),

            "avg_drawings_per_job":
                total_drawings / len(received)
                if len(received) else 0,

            "avg_turnaround_days":
                completed["turnaround_days"].mean()
                if len(completed) else 0,
        })

    return pd.DataFrame(rows).fillna(0)

def draughtsman_summary(df):
    rows=[]
    for _,r in df.iterrows():
        for p in [x.strip() for x in str(r["assignees"]).split("|") if x.strip()]:
            rows.append({"draughtsman":p,"job_number":r["job_number"],"credited_drawings":r["credited_drawings_per_person"],"turnaround_days":r["turnaround_days"],"waiting_days":r["waiting_days"],"active_days":r["active_days"]})
    if not rows: return pd.DataFrame(columns=["draughtsman","jobs","credited_drawings","avg_turnaround_days"])
    x=pd.DataFrame(rows)
    return x.groupby("draughtsman",as_index=False).agg(jobs=("job_number","count"),credited_drawings=("credited_drawings","sum"),avg_turnaround_days=("turnaround_days","mean")).fillna(0)

def current_workload(df):
    x=df[df["stage"].isin(["Not Started","In Progress","On Hold"])].copy()
    if x.empty: return x
    x["job_age_days"]=(pd.Timestamp.now()-x["created_at"]).dt.total_seconds()/86400
    cols=["assignees","job_number","customer","description","stage","priority","drawing_count","created_at","job_age_days","deadline"]
    return x[[c for c in cols if c in x.columns]].sort_values(["assignees","stage","created_at"])
