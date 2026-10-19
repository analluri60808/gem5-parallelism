"""Fresh Part 2 experiments: x86 O3, width 1/4, predictor bypass, 1/2 threads."""
import argparse
import json
import os
from pathlib import Path
import m5
from m5.objects import *

p = argparse.ArgumentParser()
p.add_argument('--width', type=int, choices=[1, 4], default=1)
p.add_argument('--bp', choices=['local', 'off'], default='local')
p.add_argument('--btb-index', choices=['auto','one'], default='auto')
p.add_argument('--programs', nargs='+', required=True)
p.add_argument('--max-ticks', type=int, default=2_000_000_000)
a = p.parse_args()
assert 1 <= len(a.programs) <= 2
assert ('GEM5_ILP_DISABLE_BP' in os.environ) == (a.bp == 'off'), 'BP mode/environment mismatch'

system = System()
system.clk_domain = SrcClockDomain(clock='2GHz', voltage_domain=VoltageDomain())
system.mem_mode = 'timing'
system.multi_thread = len(a.programs) > 1
system.mem_ranges = [AddrRange('512MiB')]
system.cpu = X86O3CPU(numThreads=len(a.programs))
cpu = system.cpu
# O3 has Fetch, Decode, Rename, IEW, Commit. Memory and writeback occur
# within IEW; this is explicitly NOT a literal five-stage in-order CPU.
for field in ('fetchWidth', 'decodeWidth', 'renameWidth', 'dispatchWidth',
              'issueWidth', 'wbWidth', 'commitWidth'):
    setattr(cpu, field, a.width)
cpu.fetchToDecodeDelay = 1
cpu.decodeToRenameDelay = 1
cpu.renameToIEWDelay = 1
cpu.issueToExecuteDelay = 1
cpu.iewToCommitDelay = 1
cpu.numROBEntries = 128
cpu.numPhysIntRegs = 256
cpu.numPhysFloatRegs = 256
cpu.numPhysCCRegs = 256
cpu.LQEntries = 32
cpu.SQEntries = 32
cpu.instQueues = [IQUnit(numEntries=64, smtIQPolicy='Partitioned')]
cpu.smtROBPolicy = 'Partitioned'
cpu.smtLSQPolicy = 'Partitioned'
cpu.smtFetchPolicy = 'RoundRobin'
cpu.smtCommitPolicy = 'RoundRobin'
cpu.smtNumFetchingThreads = 1
cpu.branchPred = BranchPredictor(conditionalBranchPred=LocalBP(
    localPredictorSize=2048, localCtrBits=2))
# This gem5 revision defaults the nested BTB indexer to one thread even
# when the BTB has two contexts. Set it explicitly; 'one' is a sensitivity run.
cpu.branchPred.btb.btbIndexingPolicy.numThreads = len(a.programs) if a.btb_index == 'auto' else 1
system.membus = SystemXBar()
system.icache = Cache(size='16KiB', assoc=2, tag_latency=2,
    data_latency=2, response_latency=2, mshrs=8, tgts_per_mshr=8)
system.dcache = Cache(size='16KiB', assoc=2, tag_latency=2,
    data_latency=2, response_latency=2, mshrs=8, tgts_per_mshr=8)
cpu.icache_port = system.icache.cpu_side
cpu.dcache_port = system.dcache.cpu_side
system.icache.mem_side = system.membus.cpu_side_ports
system.dcache.mem_side = system.membus.cpu_side_ports
cpu.createInterruptController()
for interrupt in cpu.interrupts:
    interrupt.pio = system.membus.mem_side_ports
    interrupt.int_requestor = system.membus.cpu_side_ports
    interrupt.int_responder = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports
system.memory = SimpleMemory(range=system.mem_ranges[0], latency='30ns', bandwidth='16GiB/s')
system.memory.port = system.membus.mem_side_ports
system.workload = SEWorkload.init_compatible(str(Path(a.programs[0]).resolve()))
procs = []
for tid, binary in enumerate(a.programs):
    proc = Process(pid=100+tid)
    proc.cmd = [str(Path(binary).resolve())]
    proc.output = f'thread{tid}.stdout'
    proc.errout = f'thread{tid}.stderr'
    procs.append(proc)
cpu.workload = procs
cpu.createThreads()
root = Root(full_system=False, system=system)
m5.instantiate()
print('EXPERIMENT ' + json.dumps(vars(a), sort_keys=True))
event = m5.simulate(a.max_ticks)
print(f'EXIT tick={m5.curTick()} cause={event.getCause()} code={event.getCode()}')
if 'last active thread context' not in event.getCause():
    raise RuntimeError('Workload did not complete: ' + event.getCause())
