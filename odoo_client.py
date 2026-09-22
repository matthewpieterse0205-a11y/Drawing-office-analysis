import requests
import pandas as pd

class OdooConfigError(RuntimeError):
    pass

class OdooClient:
    def __init__(self, url, db, username, api_key, project_id=2):
        self.url=url.rstrip("/")
        self.db=db
        self.username=username
        self.api_key=api_key
        self.project_id=int(project_id)
        self.uid=None

    @classmethod
    def from_streamlit_secrets(cls, secrets):
        try:
            c=secrets["odoo"]
            return cls(c["url"],c["db"],c["username"],c["api_key"],c.get("project_id",2))
        except Exception as e:
            raise OdooConfigError("Missing Odoo secrets") from e

    def _rpc(self, service, method, args):
        payload={"jsonrpc":"2.0","method":"call","params":{"service":service,"method":method,"args":args},"id":1}
        r=requests.post(f"{self.url}/jsonrpc",json=payload,timeout=30)
        r.raise_for_status()
        j=r.json()
        if j.get("error"): raise RuntimeError(j["error"])
        return j["result"]

    def login(self):
        self.uid=self._rpc("common","login",[self.db,self.username,self.api_key])
        if not self.uid: raise OdooConfigError("Odoo login failed")
        return self.uid

    def execute_kw(self, model, method, args=None, kwargs=None):
        if self.uid is None: self.login()
        return self._rpc("object","execute_kw",[self.db,self.uid,self.api_key,model,method,args or [],kwargs or {}])

    def fetch_drawing_office_jobs(self):
        fields=["id","name","project_id","stage_id","user_ids","partner_id","date_deadline","date_last_stage_update","create_date","x_studio_priority","x_studio_requirements","x_studio_job_description","x_studio_number_of_drawings"]
        jobs=self.execute_kw("project.task","search_read",[[["project_id","=",self.project_id]]],{"fields":fields,"limit":5000})

        uids=sorted({u for j in jobs for u in (j.get("user_ids") or [])})
        users=self.execute_kw("res.users","read",[uids],{"fields":["name"]}) if uids else []
        um={u["id"]:u["name"] for u in users}

        sids=sorted({j["stage_id"][0] for j in jobs if isinstance(j.get("stage_id"),list)})
        stages=self.execute_kw("project.task.type","read",[sids],{"fields":["name"]}) if sids else []
        sm={s["id"]:s["name"] for s in stages}

        out=[]
        for j in jobs:
            sid=j["stage_id"][0] if isinstance(j.get("stage_id"),list) else None
            stage=sm.get(sid,"")
            partner=j.get("partner_id")
            out.append({
                "job_id":j["id"],
                "job_number":j.get("name") or "",
                "customer":partner[1] if isinstance(partner,list) and len(partner)>1 else "",
                "requirements":j.get("x_studio_requirements") or "",
                "drawing_count":j.get("x_studio_number_of_drawings"),
                "assignees":"|".join(um.get(uid,f"User {uid}") for uid in (j.get("user_ids") or [])),
                "stage":stage,
                "priority":j.get("x_studio_priority") or "",
                "description":j.get("x_studio_job_description") or "",
                "created_at":j.get("create_date"),
                "completed_at":j.get("date_last_stage_update") if stage=="Completed" else None,
                "first_stage_change_at":None,
                "deadline":j.get("date_deadline"),
            })
        return pd.DataFrame(out)
