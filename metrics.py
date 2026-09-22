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

def apply_filters(df,start_date,end_date,people,customers,job_types,priorities,stages,job_search):
    x=df[(df["created_at"].dt.date>=start_date)&(df["created_at"].dt.date<=end_date)].copy()
    if people: x=x[x["assignees"].apply(lambda s:any(p in [q.strip() for q in str(s).split("|")] for p in people))]
    if customers: x=x[x["customer"].isin(customers)]
    if job_types: x=x[x["job_type"].isin(job_types)]
    if priorities: x=x[x["priority"].isin(priorities)]
    if stages: x=x[x["stage"].isin(stages)]
    if job_search: x=x[x["job_number"].astype(str).str.contains(job_search,case=False,na=False)]
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

def monthly_summary(df):
    if df.empty: return pd.DataFrame(columns=["month","jobs_received","jobs_completed","total_drawings","new_drawings","release_drawings","avg_drawings_per_job","avg_turnaround_days","avg_waiting_days","avg_active_days","avg_time_per_drawing_days"])
    x=df.copy(); x["month"]=x["created_at"].dt.to_period("M").astype(str)
    rows=[]
    for m,g in x.groupby("month",sort=True):
        c=g[g["completed_at"].notna()]; td=g["drawing_count"].fillna(0).sum()
        rows.append({"month":m,"jobs_received":len(g),"jobs_completed":len(c),"total_drawings":td,
        "new_drawings":g.loc[g["job_type"]=="New","drawing_count"].fillna(0).sum(),
        "release_drawings":g.loc[g["job_type"]=="Release","drawing_count"].fillna(0).sum(),
        "avg_drawings_per_job":td/len(g) if len(g) else 0,
        "avg_turnaround_days":c["turnaround_days"].mean(),"avg_waiting_days":c["waiting_days"].mean(),
        "avg_active_days":c["active_days"].mean(),"avg_time_per_drawing_days":c["time_per_drawing_days"].mean()})
    return pd.DataFrame(rows).fillna(0)

def draughtsman_summary(df):
    rows=[]
    for _,r in df.iterrows():
        for p in [x.strip() for x in str(r["assignees"]).split("|") if x.strip()]:
            rows.append({"draughtsman":p,"job_number":r["job_number"],"credited_drawings":r["credited_drawings_per_person"],"turnaround_days":r["turnaround_days"],"waiting_days":r["waiting_days"],"active_days":r["active_days"]})
    if not rows: return pd.DataFrame(columns=["draughtsman","jobs","credited_drawings","avg_turnaround_days","avg_waiting_days","avg_active_days"])
    x=pd.DataFrame(rows)
    return x.groupby("draughtsman",as_index=False).agg(jobs=("job_number","count"),credited_drawings=("credited_drawings","sum"),avg_turnaround_days=("turnaround_days","mean"),avg_waiting_days=("waiting_days","mean"),avg_active_days=("active_days","mean")).fillna(0)

def current_workload(df):
    x=df[df["stage"].isin(["Not Started","In Progress","On Hold"])].copy()
    if x.empty: return x
    x["job_age_days"]=(pd.Timestamp.now()-x["created_at"]).dt.total_seconds()/86400
    cols=["assignees","job_number","customer","description","stage","priority","drawing_count","created_at","job_age_days","deadline"]
    return x[[c for c in cols if c in x.columns]].sort_values(["assignees","stage","created_at"])
