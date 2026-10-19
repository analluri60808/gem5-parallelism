"""Explicit educational F/D/E/M/W model scheduled on gem5's event queue.

This is a small custom token machine, not an x86 CPU or an O3 substitute.
One-cycle stages, in-order, no forwarding, WB writes before E operand read.
The separate O3 experiments use native gem5 statistics and x86 workloads.
"""
import csv, json
from pathlib import Path
import m5
from m5.objects import Root
from m5.event import Event, getEventQueue
from _m5.event import exitSimLoop

root=Root(full_system=False)
m5.instantiate()
PERIOD=500
program=[
    dict(op='LI',dst='r1',src=[],imm=5),
    dict(op='LI',dst='r2',src=[],imm=3),
    dict(op='ADD',dst='r3',src=['r1','r2']),
    dict(op='LD',dst='r4',src=[],addr=0),
    dict(op='ADD',dst='r5',src=['r3','r4']),
    dict(op='ST',dst=None,src=['r5'],addr=8),
    dict(op='ADD',dst='r6',src=['r1','r2']),
    dict(op='ADD',dst='r7',src=['r6','r5']),
]
class Pipeline(Event):
    def __init__(self):
        super().__init__()
        self.q=getEventQueue(0); self.slots=[None]*5
        self.regs={}; self.mem={0:7}; self.pc=0; self.cycle=0
        self.rows=[]; self.done=[]; self.stalls=0
        self.q.schedule(self,PERIOD)
    def __call__(self):
        self.cycle+=1
        f,d,e,mem,w=self.slots
        # Advance older instructions, then write back before reading operands.
        w=mem
        if w is not None:
            if w['dst']: self.regs[w['dst']]=w['value']
            w['retire_cycle']=self.cycle; self.done.append(w)
        mem=e
        if mem is not None:
            if mem['op']=='LD': mem['value']=self.mem[mem['addr']]
            if mem['op']=='ST': self.mem[mem['addr']]=mem['value']
        hazards=set([mem['dst']]) if mem and mem['dst'] else set()
        stall=d is not None and bool(hazards.intersection(d['src']))
        if stall:
            e=None; self.stalls+=1
        else:
            e=d
            if e is not None:
                vals=[self.regs[r] for r in e['src']]
                if e['op']=='LI': e['value']=e['imm']
                if e['op']=='ADD': e['value']=sum(vals)
                if e['op']=='ST': e['value']=vals[0]
            d=f
            if self.pc<len(program):
                f=dict(program[self.pc],id=self.pc,fetch_cycle=self.cycle)
                self.pc+=1
            else: f=None
        self.slots=[f,d,e,mem,w]
        row={'cycle':self.cycle,'tick':int(m5.curTick()),
             **{stage:('I'+str(ins['id'])) if ins else '-' for stage,ins in zip(['F','D','E','M','W'],self.slots)},
             'stall':int(stall)}
        self.rows.append(row)
        print('CYCLE ' + ' '.join(f'{k}={v}' for k,v in row.items()))
        if len(self.done)==len(program):
            assert self.regs=={'r1':5,'r2':3,'r3':8,'r4':7,'r5':15,'r6':8,'r7':23}
            assert self.mem[8]==15
            exitSimLoop('five-stage complete', 0, m5.curTick(), 0, False)
        else: self.q.schedule(self,m5.curTick()+PERIOD)
pipeline=Pipeline()
event=m5.simulate(100_000)
assert event.getCause()=='five-stage complete'
out=Path(m5.options.outdir)
with open(out/'cycles.csv','w') as f:
    writer=csv.DictWriter(f,fieldnames=pipeline.rows[0]); writer.writeheader(); writer.writerows(pipeline.rows)
summary={'model':'custom educational gem5 event-queue pipeline','period_ticks':PERIOD,
         'cycles':pipeline.cycle,'instructions':len(pipeline.done),
         'ipc':len(pipeline.done)/pipeline.cycle,'stall_cycles':pipeline.stalls,
         'mean_latency_cycles':sum(i['retire_cycle']-i['fetch_cycle']+1 for i in pipeline.done)/len(pipeline.done),
         'registers':pipeline.regs,'memory':pipeline.mem,'instructions_detail':pipeline.done}
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print('RESULT '+json.dumps(summary))
