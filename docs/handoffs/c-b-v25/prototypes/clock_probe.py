"""Early-timer demonstration (stdlib only; NOT repository code). asyncio runs scheduled handles whose time is < loop.time() + _clock_resolution,
i.e. up to one clock resolution EARLY (CPython base_events.py _run_once). The loop's private _clock_resolution is patched to emulate a coarse clock
(e.g. ~15.6 ms on Windows for 3.11/3.12 -- real Windows value UNVERIFIED). Plain >= comparisons miss a phase; tolerance of one resolution does not."""
import asyncio, enum
class St(enum.Enum): RUNNING="RUNNING"; STOPPING="STOPPING"; STOPPED="STOPPED"; ABANDONED="ABANDONED"
class Task(asyncio.Task):
    cancel_calls=0
    def cancel(self,msg=None): self.cancel_calls+=1; return super().cancel(msg)
class W:
    def __init__(s,f,te,cg): s.f=f;s.te=te;s.cg=cg;s.st=St.RUNNING;s.esc=False;s.cr=False;s.out=None;s.res=0.0;s.handles=[]
    def due(s,when): return s.loop.time()>=when                       # v2.4: plain >=
    def start(s): s.loop=asyncio.get_running_loop(); s.task=asyncio.create_task(s.f())
    def advance(s):
        t=s.task
        if t.done() or not s.cr: return
        if s.due(s.e) and not s.esc: s.esc=True; t.cancel()
        if s.due(s.a) and s.st is St.STOPPING: s.st=St.ABANDONED; s.out="timed_out"
    async def stop(s):
        s.e=s.loop.time()+s.te; s.a=s.e+s.cg; s.cr=True; s.st=St.STOPPING; s.task.cancel()
        s.handles=[s.loop.call_at(s.e,s.advance),s.loop.call_at(s.a,s.advance)]
        rem=s.a-s.loop.time()
        if rem>0: await asyncio.wait({s.task},timeout=rem)
        s.advance()
        return s.out if s.st is not St.STOPPING else None
class WT(W):
    def due(s,when): return s.loop.time()+s.res>=when                 # tolerance = clock resolution (Model A)
async def main():
    loop=asyncio.get_running_loop(); loop.set_task_factory(lambda l,c,**kw: Task(c,loop=l,**kw))
    RES=0.03; loop._clock_resolution=RES
    async def swall(rel):
        while not rel.is_set():
            try: await asyncio.sleep(0.01)
            except asyncio.CancelledError: pass
    for label,cls in (("plain >= comparisons",W),("tolerance = clock resolution",WT)):
        rel=asyncio.Event(); w=cls(lambda: swall(rel),0.1,0.1); w.res=RES; w.start(); await asyncio.sleep(0)
        r=await w.stop(); await asyncio.sleep(0.4)
        print(f"{label}: stop() returned {r}; state={w.st.value}; cancel_calls={w.task.cancel_calls}; outcome={w.out}")
        rel.set(); await asyncio.sleep(0.05)
asyncio.run(main())
