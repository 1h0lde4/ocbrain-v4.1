"""Design-validation toy v2.4 (stdlib only; NOT repository code; algorithm evidence only).
Reproduces the two v2.3 defects (IDLE local-assignment bug; caller cancellation bypassing escalation) and validates
the v2.4 supervision contract: ONE await-free _advance() driven by (a) loop timers owned by the watchdog and (b) stop() callers.
KNOWN DEFECTS of this v2.4 toy (to be fixed in v2.5, see handoff.md F-01/F-02/F-03): _advance() checks _cancel_requested before
task.done(); stop() waits before calling _advance(); deadline comparisons are plain >= (early timers can miss a phase on coarse clocks)."""
import asyncio, enum, math, gc, weakref, threading
class Out(enum.Enum): STOPPED="stopped"; CHILD_ERROR="child_error"; TIMED_OUT="timed_out"; NOT_STARTED="not_started"
class St(enum.Enum): IDLE="IDLE"; RUNNING="RUNNING"; STOPPING="STOPPING"; STOPPED="STOPPED"; ABANDONED="ABANDONED"
class CTask(asyncio.Task):
    cancel_calls=0; exception_calls=0
    def cancel(self,msg=None): self.cancel_calls+=1; return super().cancel(msg)
    def exception(self): self.exception_calls+=1; return super().exception()
def cfg(n,v):
    if isinstance(v,bool) or not isinstance(v,(int,float)): raise TypeError(n)
    if not math.isfinite(v) or v<0: raise ValueError(n)
    return float(v)
class V23:       # v2.3 as published: IDLE branch assigns LOCALS; caller cancellation skips escalation (no timers)
    def __init__(s,f,stop_timeout=0.1,cancel_grace=0.1): s._f=f;s._st=St.IDLE;s._task=None;s._outcome=None;s._cr=False;s._esc=False;s.et=stop_timeout;s.cg=cancel_grace
    def start(s):
        if s._st is not St.IDLE: raise RuntimeError("single-use")
        s._task=asyncio.create_task(s._f()); s._st=St.RUNNING
    async def stop(s):
        if s._st is St.IDLE:
            state=St.STOPPED; outcome=Out.NOT_STARTED; return outcome          # BUG: locals, not instance attributes
        t=s._task; loop=asyncio.get_running_loop()
        if not s._cr: s._cr=True; s._e=loop.time()+s.et; s._a=s._e+s.cg; s._st=St.STOPPING; t.cancel()
        done,_=await asyncio.wait({t},timeout=max(0,s._e-loop.time()))
        if not t.done():
            if not s._esc: s._esc=True; t.cancel()
            await asyncio.wait({t},timeout=max(0,s._a-loop.time()))
        return Out.STOPPED if t.done() else Out.TIMED_OUT
class W:         # v2.4
    def __init__(s,f,stop_timeout=0.15,cancel_grace=0.15):
        s._f=f; s.stop_timeout=cfg("stop_timeout",stop_timeout); s.cancel_grace=cfg("cancel_grace",cancel_grace)
        s._task=None; s._loop=None; s._state=St.IDLE; s._cancel_requested=False; s._escalated=False; s._escalate_at=s._abandon_at=None
        s._outcome=None; s._finalized=False; s.task_result=None; s.child_exception=None; s._handles=[]; s.abandon_count=0
    def start(s):
        if s._state is not St.IDLE: raise RuntimeError("single-use")
        s._loop=asyncio.get_running_loop(); s._task=asyncio.create_task(s._f()); s._state=St.RUNNING; s._task.add_done_callback(s._finalize)
    def _finalize(s,task):                                   # lifecycle bookkeeping only (v2.2.1 section 4 + timer cancellation)
        if s._finalized or s._task is not task: return
        if not task.done(): return
        s._finalized=True
        for h in s._handles: h.cancel()
        s._handles.clear()
        if task.cancelled(): s.task_result="cancelled"
        else:
            e=task.exception()
            if e is None: s.task_result="finished"
            else: s.task_result="error"; s.child_exception=e
        if s._outcome is None: s._outcome=Out.CHILD_ERROR if s.task_result=="error" else Out.STOPPED
        s._task=None; s._state=St.STOPPED
    def _advance(s):                                         # the ONLY place phases advance; await-free, idempotent, never raises
        t=s._task
        if s._finalized or t is None or not s._cancel_requested: return          # NOTE (F-01): checks _cancel_requested BEFORE task.done()
        if t.done(): s._finalize(t); return                  # I8
        now=s._loop.time()
        if now>=s._escalate_at and not s._escalated: s._escalated=True; t.cancel()        # NOTE (F-03): plain >=
        if now>=s._abandon_at and s._state is St.STOPPING:
            s._state=St.ABANDONED; s._outcome=Out.TIMED_OUT; s.abandon_count+=1
            assert s._escalated
    def _check_loop(s):
        if s._state in (St.RUNNING,St.STOPPING,St.ABANDONED) and asyncio.get_running_loop() is not s._loop: raise RuntimeError("other loop")
    async def stop(s):
        s._check_loop()
        if s._state is St.IDLE: s._state=St.STOPPED; s._outcome=Out.NOT_STARTED; return s._outcome      # explicit instance attributes
        if s._state is St.STOPPED: return s._outcome
        t=s._task
        if t is asyncio.current_task(): raise RuntimeError("stop() must not be called from the watchdog task")
        if not t.done() and not s._cancel_requested:
            loop=asyncio.get_running_loop(); e=loop.time()+s.stop_timeout; a=e+s.cancel_grace
            if not (math.isfinite(e) and math.isfinite(a)): raise RuntimeError("non-finite computed deadline")
            s._cancel_requested=True; s._escalate_at=e; s._abandon_at=a; s._state=St.STOPPING
            t.cancel()
            s._handles=[loop.call_at(e,s._advance),loop.call_at(a,s._advance)]        # timers: loop callbacks, NOT tasks
        if t is not None and not t.done() and s._state is St.STOPPING:
            rem=s._abandon_at-asyncio.get_running_loop().time()                       # NOTE (F-02): waits BEFORE advancing
            if rem>0: await asyncio.wait({t},timeout=rem)
        if s._task is not None and s._task.done(): s._finalize(s._task)
        else: s._advance()
        return s._outcome if s._state is St.STOPPED else (Out.TIMED_OUT if s._state is St.ABANDONED else None)
def kids():
    async def prompt(): await asyncio.sleep(3600)
    def held_cleanup(gin,grel,rec):
        async def f():
            try: await asyncio.sleep(3600)
            except asyncio.CancelledError:
                gin.set()
                try: await grel.wait(); rec["cleanup"]="completed"
                except asyncio.CancelledError: rec["cleanup"]="interrupted by escalation"; raise
        return f
    def swallower(release,then_raise=False):
        async def f():
            while True:
                try: await release.wait(); break
                except asyncio.CancelledError: pass
            if then_raise: raise RuntimeError("late failure")
        return f
    return prompt,held_cleanup,swallower
async def main():
    loop=asyncio.get_running_loop(); loop.set_task_factory(lambda l,c,**kw: CTask(c,loop=l,**kw))
    hc=[]; loop.set_exception_handler(lambda l,c: hc.append(c.get("message","")[:50])); R={}
    prompt,held,swall=kids()
    w=V23(prompt); o=await w.stop()
    try: w.start(); s="start() SUCCEEDED (single-use violated)"
    except RuntimeError: s="start() raised"
    R["1 v2.3 IDLE stop()"]=(o.value,"state_after_the_later_start()="+w._st.value,s)
    if w._task: w._task.cancel(); await asyncio.sleep(0)
    w=W(prompt); o=await w.stop()
    try: w.start(); s="BUG"
    except RuntimeError: s="start() raised"
    R["1 v2.4 IDLE stop()"]=(o.value,"state="+w._state.value,"outcome sticky="+w._outcome.value,s)
    for label,cls in (("v2.3 (supervision tied to the caller)",V23),("v2.4 (timer-driven supervision)",W)):
        gin,grel,rec=asyncio.Event(),asyncio.Event(),{}
        w=cls(held(gin,grel,rec),0.1,0.1); w.start(); await asyncio.sleep(0); t=w._task
        c=asyncio.create_task(w.stop()); await gin.wait(); c.cancel(); await asyncio.gather(c,return_exceptions=True)
        await asyncio.sleep(0.35)
        st=(getattr(w,'_st',None) or w._state).value
        R[f"2a R10 cleanup child, caller cancelled, {label}"]=(f"caller.cancelled={c.cancelled()}",f"cancel_calls={t.cancel_calls}",f"cleanup={rec.get('cleanup','still pending')}",f"state={st}",f"child_done={t.done()}")
        grel.set(); await asyncio.sleep(0.02)
    for label,cls in (("v2.3",V23),("v2.4",W)):
        rel=asyncio.Event(); w=cls(swall(rel),0.1,0.1); w.start(); await asyncio.sleep(0); t=w._task
        c=asyncio.create_task(w.stop()); await asyncio.sleep(0.02); c.cancel(); await asyncio.gather(c,return_exceptions=True); await asyncio.sleep(0.35)
        st=(getattr(w,'_st',None) or w._state).value
        R[f"2b R10 cancel-suppressing child, caller cancelled, {label}"]=(f"cancel_calls={t.cancel_calls}",f"state={st}",f"outcome={getattr(w,'_outcome',None) and w._outcome.value}")
        rel.set(); await asyncio.sleep(0.05)
    for label,raise_ in (("normal",False),("raises",True)):
        rel=asyncio.Event(); w=W(swall(rel,raise_),0.05,0.05); w.start(); await asyncio.sleep(0); t=w._task
        o=await w.stop(); st1=(o.value,w._state.value,f"abandon_entries={w.abandon_count}",f"cancel_calls={t.cancel_calls}")
        rel.set(); await asyncio.sleep(0.1)
        ref=weakref.ref(w); res=(w._state.value,w._outcome.value,w.task_result,type(w.child_exception).__name__,f"exception_calls={t.exception_calls}","_task_cleared="+str(w._task is None),"timers_cleared="+str(not w._handles))
        del w,t; gc.collect(); R[f"3 T-B29 abandoned child finishes later ({label})"]=(st1,res,"watchdog_collectable="+str(ref() is None),f"handler_calls={len(hc)}")
    await asyncio.sleep(0.05); leaked=[x for x in asyncio.all_tasks() if x is not asyncio.current_task() and not x.done()]
    R["leaked pending tasks"]=len(leaked); R["loop handler calls"]=len(hc); return R
for k,v in asyncio.run(main()).items(): print(f"{k}: {v}")
