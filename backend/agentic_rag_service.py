"""Agentic self-healing + RAG service. Planner -> Exec -> Critic; JSON-bound, temperature 0, seed locked."""
import json, os, httpx, asyncpg, jwt
from typing import Literal, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app, emb, bearer = FastAPI(title="FlowLab Agents"), SentenceTransformer("all-MiniLM-L6-v2"), HTTPBearer(auto_error=False)
JWKS = jwt.PyJWKClient(os.environ["OIDC_JWKS_URL"]) if os.environ.get("OIDC_JWKS_URL") else None

def auth(c=Depends(bearer)):
    if not JWKS:
        if os.environ.get("ENV") == "dev": return {"role": "dev"}
        raise HTTPException(401, "OIDC not configured")                       # fail closed
    if not c: raise HTTPException(401, "missing token")
    return jwt.decode(c.credentials, JWKS.get_signing_key_from_jwt(c.credentials).key,
                      algorithms=["RS256"], audience=os.environ["OIDC_AUD"])

class Diagnosis(BaseModel):
    action: Literal["retry", "skip", "abort"]; input: Optional[dict] = None; destructive: bool = False; reason: str
class Failure(BaseModel): workflow_id: str; step: str; error: str; context: dict = {}
class Intent(BaseModel): text: str

async def llm(system, user, shape):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
            json={"model": "llama-3.3-70b-versatile", "temperature": 0, "seed": 7, "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": system + " Reply ONLY JSON like: " + json.dumps(shape)},
                               {"role": "user", "content": user}]})
    return json.loads(r.json()["choices"][0]["message"]["content"])

@app.on_event("startup")
async def up(): app.state.db = await asyncpg.create_pool(os.environ["DATABASE_URL"])

async def rag(q, k=3):
    v = str(emb.encode(q).tolist())
    return [r["content"] for r in await app.state.db.fetch("SELECT content FROM documents ORDER BY embedding <=> $1::vector LIMIT $2", v, k)]

@app.post("/plan")
async def plan(i: Intent, _=Depends(auth)):
    return await llm("You are the Planner. Output ordered workflow step names.", i.text + "\nContext: " + " | ".join(await rag(i.text)), {"steps": ["..."]})

@app.post("/diagnose", response_model=Diagnosis)
async def diagnose(f: Failure, _=Depends(auth)):
    ctx = await rag(f"{f.step} {f.error}")
    d = Diagnosis(**await llm("You are the Exec agent. Diagnose the failed step; prefer non-destructive retry.",
        json.dumps({**f.dict(), "knowledge": ctx}), {"action": "retry|skip|abort", "input": {}, "destructive": False, "reason": ""}))
    c = await llm("You are the Critic. Approve only safe, reversible remediations.", d.json(), {"approve": True})
    if not c.get("approve"): d.destructive = True                              # Critic veto -> human-in-the-loop
    return d
