#!/usr/bin/env python3
"""Compile original workloads and run fresh simulations. Never reads old measurements."""
import argparse, datetime, hashlib, json, os, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAMES=['integer','floating','memory','branch_biased','branch_random','dependent']
def call(cmd, **kw):
    return subprocess.run([str(x) for x in cmd], check=True, **kw)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--gem5-root', default='/home/madan/gem5')
    p.add_argument('--batch', default='verified-fresh-20261018')
    p.add_argument('--only', nargs='*')
    a=p.parse_args(); gem=pathlib.Path(a.gem5_root); binary=gem/'build/X86/gem5.opt'
    out=ROOT/'results'/a.batch
    out.mkdir(exist_ok=True, parents=True)
    for kind,name in enumerate(NAMES):
        cmd=['gcc','-O2','-fno-tree-vectorize','-fno-unroll-loops','-fno-stack-protector','-fno-pie','-no-pie',
             '-nostdlib','-static','-Wl,--build-id=none',f'-DKIND={kind}',ROOT/'workloads/start.S',ROOT/'workloads/bench.c','-o',ROOT/'bin'/name]
        call(cmd)
        with open(ROOT/'bin'/f'{name}.asm','w') as f: call(['objdump','-d',ROOT/'bin'/name],stdout=f)
    native={name:subprocess.check_output([ROOT/'bin'/name]).decode() for name in NAMES}
    cases=[]
    for name in NAMES:
        cases += [(f'{name}_w{w}_local',w,'local',[name]) for w in [1,4]]
    for name in ['branch_biased','branch_random']:
        cases += [(f'{name}_w{w}_off',w,'off',[name]) for w in [1,4]]
    for pair in [('integer','floating'),('dependent','dependent'),('memory','integer'),('memory','memory')]:
        cases += [(f'smt_{pair[0]}_{pair[1]}',4,'local',list(pair))]
        cases += [(f'smt_{pair[0]}_{pair[1]}_btb1',4,'local',list(pair))]
    meta={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'gem5_root':str(gem),'gem5_commit':subprocess.check_output(['git','-C',gem,'rev-parse','HEAD']).decode().strip(),
          'gem5_sha256':sha(binary),'gcc':subprocess.check_output(['gcc','--version']).decode().splitlines()[0],
          'native_checksums':native,'binary_sha256':{n:sha(ROOT/'bin'/n) for n in NAMES}}
    (out/'provenance.json').write_text(json.dumps(meta,indent=2))
    for name,w,bp,programs in cases:
        if a.only and name not in a.only: continue
        dest=out/name
        if dest.exists(): raise FileExistsError(f'Refusing to overwrite results: {dest}')
        dest.mkdir()
        cmd=[binary,f'--outdir={dest}','--debug-flags=O3PipeView','--debug-file=pipeline.trace.gz',
             ROOT/'configs/ilp.py','--width',str(w),'--bp',bp,'--btb-index',
             'one' if name.endswith('_btb1') else 'auto','--programs',*[ROOT/'bin'/n for n in programs]]
        env=os.environ.copy(); env.pop('GEM5_ILP_DISABLE_BP',None)
        if bp=='off': env['GEM5_ILP_DISABLE_BP']='1'
        record={'name':name,'width':w,'bp':bp,'programs':programs,'command':list(map(str,cmd)),
                'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bp_bypass':bp=='off'}
        print(f'RUN {name}',flush=True)
        with open(dest/'console.log','w') as f: call(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
        for tid,prog in enumerate(programs):
            actual=(dest/f'thread{tid}.stdout').read_text()
            if actual != native[prog]: raise AssertionError((name,tid,actual,native[prog]))
        record['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['checksums_verified']=True
        (dest/'run.json').write_text(json.dumps(record,indent=2))
        print(f'PASS {name}',flush=True)
    print('Batch complete',flush=True)
if __name__=='__main__': main()
