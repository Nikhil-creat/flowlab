"""FlowLab durable engine: event-sourced, write-ahead, replay-safe."""
import asyncio, json, os, random, time, asyncpg
import redis.asyncio as aioredis
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = bytes.fromhex(os.environ.get("FIELD_KEY_HEX", "00" * 32))  # AES-256 key: set a real one in prod
def enc(o): n = os.urandom(12); return n + AESGCM(KEY).encrypt(n, json.dumps(o).encode(), None)
def dec(b): b = bytes(b); return json.loads(AESGCM(KEY).decrypt(b[:12], b[12:], None))

class Breaker:
    def __init__(s, limit=3, cool=30): s.n, s.t, s.limit, s.cool = 0, 0.0, limit, cool
    def allow(s): return s.n < s.limit or time.monotonic() - s.t > s.cool
    def ok(s): s.n = 0
    def fail(s): s.n += 1; s.t = time.monotonic()

class Engine:
    """Workflow logic stays deterministic: all I/O, time and randomness live inside activities."""
    def __init__(s, db, redis, activities, diagnose=None, retries=4):
        s.db, s.r, s.act, s.diag, s.retries = db, redis, activities, diagnose, retries
        s.br = {k: Breaker() for k in activities}

    async def history(s, wf):
        return await s.db.fetch("SELECT * FROM events WHERE workflow_id=$1 ORDER BY seq", wf)

    async def log(s, wf, typ, step=None, attempt=1, payload=None):
        """Write-ahead append. The unique idem_key turns a re-append after a crash into a no-op."""
        await s.db.execute(
            "INSERT INTO events(workflow_id,seq,type,step_id,attempt,payload,idem_key) VALUES($1,"
            "(SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE workflow_id=$1),$2,$3,$4,$5,$6) ON CONFLICT (idem_key) DO NOTHING",
            wf, typ, step, attempt, enc(payload) if payload is not None else None, f"{wf}:{step}:{attempt}:{typ}")

    async def run(s, wf, steps, ctx=None):
        ctx = ctx or {}
        await s.db.execute("INSERT INTO workflows(id,name) VALUES($1,$1) ON CONFLICT DO NOTHING", wf)
        async with s.r.lock(f"lock:{wf}", timeout=120):              # single writer per workflow
            done = {e["step_id"]: dec(e["payload"]) for e in await s.history(wf) if e["type"] == "STEP_COMPLETED"}
            for st in steps:
                if st in done: ctx[st] = done[st]; continue           # replay: no repeated side effect
                ctx[st] = await s.step(wf, st, ctx)
            await s.log(wf, "WORKFLOW_COMPLETED")
            await s.db.execute("UPDATE workflows SET status='COMPLETED' WHERE id=$1", wf)
        return ctx

    async def step(s, wf, st, ctx):
        total = sum(1 for e in await s.history(wf) if e["step_id"] == st and e["type"] == "ACTIVITY_FAILED")
        tries, patched = 0, False
        while True:
            attempt = total + 1
            await s.log(wf, "STEP_STARTED", st, attempt)              # logged BEFORE the side effect
            if not s.br[st].allow(): raise RuntimeError(f"circuit open: {st}")
            try:
                out = await asyncio.wait_for(s.act[st](ctx, idem=f"{wf}:{st}:{attempt}"), 30)
                s.br[st].ok(); await s.log(wf, "STEP_COMPLETED", st, attempt, out); return out
            except Exception as ex:
                s.br[st].fail(); total += 1; tries += 1
                await s.log(wf, "ACTIVITY_FAILED", st, attempt, {"error": repr(ex)})
                if tries < s.retries: await asyncio.sleep(min(2 ** tries, 30) + random.random()); continue
                fix = await s.diag(wf, st, repr(ex), ctx) if s.diag and not patched else None
                if fix and fix.get("action") == "retry" and not fix.get("destructive"):
                    patched, tries = True, 0; ctx[st + ".patch"] = fix.get("input"); s.br[st] = Breaker()
                    await s.log(wf, "AGENT_REMEDIATION", st, attempt, fix); continue
                if fix and fix.get("destructive"): await s.log(wf, "HITL_REQUIRED", st, attempt, fix)
                await s.db.execute("INSERT INTO dlq(workflow_id,step_id,error) VALUES($1,$2,$3)", wf, st, repr(ex))
                await s.log(wf, "DEAD_LETTERED", st, attempt); raise

async def main():  # demo: run twice with the same id; the second run replays and repeats nothing
    db = await asyncpg.create_pool(os.environ["DATABASE_URL"]); r = aioredis.from_url(os.environ["REDIS_URL"])
    def mk(name):
        async def f(ctx, idem): print("side effect", name, idem); return {"ok": True}
        return f
    acts = {n: mk(n) for n in ["validate", "payment", "inventory", "notify"]}
    eng = Engine(db, r, acts)
    for _ in range(2): print(await eng.run("order-1001", list(acts)))
if __name__ == "__main__": asyncio.run(main())
