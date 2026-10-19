#!/usr/bin/env python3
"""Derive all published metrics from fresh raw gem5 statistics and traces."""
import csv, gzip, json, math, os, pathlib, statistics
ROOT=pathlib.Path(__file__).resolve().parents[1]
BATCH=ROOT/'results'/os.environ.get('ILP_BATCH','verified-fresh-20261018')
def stats(path):
    out={}
    for line in path.read_text().splitlines():
        parts=line.split()
        if len(parts)>1:
            try: out[parts[0]]=float(parts[1])
            except ValueError: pass
    return out
def trace(path):
    rows=[]; current=None
    with gzip.open(path,'rt') as f:
        for line in f:
            if not line.startswith('O3PipeView:'): continue
            p=line.rstrip().split(':')
            if p[1]=='fetch':
                current={'fetch':int(p[2]),'pc':p[3],'upc':int(p[4]),'seq':int(p[5]),'asm':':'.join(p[6:]).strip()}
            elif current is not None:
                current[p[1]]=int(p[2])
                if p[1]=='retire': rows.append(current); current=None
    return rows
def main():
    rows=[]
    for directory in sorted(BATCH.iterdir()):
        if not directory.is_dir(): continue
        m=json.loads((directory/'run.json').read_text()); s=stats(directory/'stats.txt')
        tr=trace(directory/'pipeline.trace.gz')
        good=[x for x in tr if x['retire']>0]
        period=s['system.clk_domain.clock']
        latency=[(x['retire']-x['fetch'])/period for x in good]
        assert all(x>=0 for x in latency)
        cycles=int(s['system.cpu.numCycles']); inst=int(s['simInsts']); ops=int(s['simOps'])
        assert len(good)<=ops
        assert len(good)/ops>0.999, 'Unexpected trace coverage gap'
        assert abs(inst/cycles-s['system.cpu.ipc'])<1e-6
        thread_inst=[int(s[f'system.cpu.commitStats{i}.numInsts']) for i in range(len(m['programs']))]
        assert sum(thread_inst)==inst
        lookups=sum(s.get(f'system.cpu.branchPred.lookups_{i}::total',0) for i in range(len(m['programs'])))
        committed=sum(s.get(f'system.cpu.branchPred.committed_{i}::total',0) for i in range(len(m['programs'])))
        misses=sum(s.get(f'system.cpu.branchPred.mispredicted_{i}::total',0) for i in range(len(m['programs'])))
        btb_misses=sum(s.get(f'system.cpu.branchPred.mispredictDueToBTBMiss_{i}::total',0) for i in range(len(m['programs'])))
        if m['bp']=='off': assert lookups==0 and committed==0
        r=dict(name=m['name'],width=m['width'],bp=m['bp'],programs='+'.join(m['programs']),threads=len(m['programs']),
            cycles=cycles,instructions=inst,micro_ops=ops,ipc=inst/cycles,uipc=ops/cycles,cpi=cycles/inst,
            trace_retired=len(good),trace_coverage=len(good)/ops,
            latency_mean=statistics.mean(latency),latency_median=statistics.median(latency),
            latency_p95=sorted(latency)[math.ceil(len(latency)*.95)-1],
            bp_lookups=int(lookups),bp_committed=int(committed),bp_mispredicted=int(misses),
            bp_btb_mispredicted=int(btb_misses),
            bp_miss_rate=misses/committed if committed else None,
            commit_branch_mispredicts=int(s.get('system.cpu.commit.branchMispredicts',0)),
            issue_slot_use=s['system.cpu.instsIssued']/(cycles*m['width']),
            fu_busy=int(s.get('system.cpu.fuBusy',s.get('system.cpu.fuBusy::total',0))),
            rename_iq_full=int(s.get('system.cpu.rename.IQFullEvents',0)),
            rename_rob_full=int(s.get('system.cpu.rename.ROBFullEvents',0)),
            rename_lq_full=int(s.get('system.cpu.rename.LQFullEvents',0)),
            rename_sq_full=int(s.get('system.cpu.rename.SQFullEvents',0)),
            rename_regs_full=int(s.get('system.cpu.rename.fullRegistersEvents',0)),
            rename_block_cycles=int(s.get('system.cpu.rename.status::Blocked',0)),
            dcache_misses=int(s.get('system.dcache.demandMisses::total',0)),
            dcache_miss_rate=s.get('system.dcache.demandMissRate::total',0),
            thread0_inst=thread_inst[0],thread1_inst=thread_inst[1] if len(thread_inst)>1 else 0)
        rows.append(r)
    by={r['name']:r for r in rows}
    for r in rows:
        r['speedup_vs_w1']=None; r['speedup_vs_serial']=None
        if r['threads']==1:
            r['speedup_vs_w1']=by[f"{r['programs']}_w1_{r['bp']}"]['cycles']/r['cycles']
        else:
            names=r['programs'].split('+')
            serial=sum(by[f'{n}_w4_local']['cycles'] for n in names)
            r['serial_cycles']=serial
            r['serial_ipc']=sum(by[f'{n}_w4_local']['instructions'] for n in names)/serial
            r['speedup_vs_serial']=serial/r['cycles']
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with open(BATCH/'summary.csv','w') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    (BATCH/'summary.json').write_text(json.dumps(rows,indent=2,allow_nan=False))
    for r in rows:
        print(f"{r['name']:29} cycles={r['cycles']:7} IPC={r['ipc']:.4f} latency={r['latency_mean']:7.2f} coverage={r['trace_coverage']:.7f} speedup={r['speedup_vs_serial'] or r['speedup_vs_w1']:.3f}")
    # Preserve a small trace excerpt with every stage timestamp for the paper.
    tr=trace(BATCH/'integer_w1_local/pipeline.trace.gz')
    selected=[r for r in sorted(tr,key=lambda r:r['seq']) if r['retire']>0 and r['seq']>=500][:16]
    (BATCH/'pipeline_excerpt.json').write_text(json.dumps(selected,indent=2))
    print('Validated: native checksums, per-thread instruction sums, IPC, trace coverage, and zero bypass lookups.')
if __name__=='__main__': main()
