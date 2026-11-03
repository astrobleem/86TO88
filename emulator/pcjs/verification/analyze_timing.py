"""Join exact digit-template readings with headless timing-mode clock samples.

Render timing snapshots first. Reads private specimen through read_counters;
no guest modifications or media writes. Results are observations, not browser QA.
"""
import argparse,json
from pathlib import Path
from read_counters import decode_pcjs,FatDisk,templates,read_frame


def analyze(fixture,evidence):
    raw,_=decode_pcjs((fixture/'disk.json').read_bytes())
    patterns=templates(FatDisk(raw).read_file('WINDOWS/WINMINE.EXE'))
    samples={}
    names={'initial','position','before-pause','paused','resumed','flag','question','blank','reset'}|{'second-'+str(i) for i in range(20,26)}
    for path in sorted(evidence.glob('timing-*.json')):
        if path.stem.removeprefix('timing-') not in names:continue
        frame=json.loads(path.read_text())
        if 'timing' not in frame or 'memory' not in frame:continue
        result=read_frame(path.with_suffix('.png'),patterns)
        result.update(frame['timing'])
        samples[path.stem.removeprefix('timing-')]=result
    needed=['second-20','second-25','before-pause','paused','resumed','flag','question','blank','reset']
    if any(n not in samples for n in needed):raise ValueError('Missing timing-mode frames')
    a,b=samples['second-20'],samples['second-25']
    elapsed=(b['hostMonotonicMs']-a['hostMonotonicMs'])/1000
    if elapsed<=0:raise ValueError('Invalid host elapsed time')
    advance=int(b['timer'])-int(a['timer'])
    before,paused=samples['before-pause'],samples['paused']
    return {'qualification':'Headless source-core timing mode; exact bitmap-mask digit readings, not browser QA',
      'timer_seconds_advanced':advance,'host_elapsed_seconds':elapsed,'observed_game_seconds_per_host_second':advance/elapsed,
      'bios_ticks_advanced':b['guestTicks']-a['guestTicks'],
      'pause_host_seconds':(paused['hostMonotonicMs']-before['hostMonotonicMs'])/1000,
      'paused_timer_unchanged':before['timer']==paused['timer'],
      'paused_guest_ticks_unchanged':before['guestTicks']==paused['guestTicks'],
      'paused_cpu_cycles_unchanged':before['cpuCycles']==paused['cpuCycles'],
      'mine_counter_after_flag':samples['flag']['mine_counter'],
      'mine_counter_after_question':samples['question']['mine_counter'],
      'mine_counter_after_blank':samples['blank']['mine_counter'],
      'mine_counter_after_reset':samples['reset']['mine_counter'],
      'timer_after_reset':samples['reset']['timer'],
      'samples':samples}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_fixture',type=Path);parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    print(json.dumps(analyze(args.private_fixture,args.evidence),indent=2))
