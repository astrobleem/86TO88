import sys, json, hashlib, pathlib, collections
sys.path.insert(0, "/tmp/unpack-main/oemdisplay-tandy-main/tools/W31CHECK")
sys.path.insert(0, "/tmp/unpack-main/oemdisplay-tandy-main")
from w31check import NEImage, analyze_bytes

winmine_path = pathlib.Path("/Users/macsd/winmine-hack/upstream/extract31/WINDOWS/WINMINE.EXE")
data = winmine_path.read_bytes()
print("WINMINE", len(data), hashlib.sha256(data).hexdigest())
img = NEImage(data, str(winmine_path))
print(f"NE offset {img.ne_offset:#x} expectedWin {img.windows_version} progFlags {img.program_flags:#x} appFlags {img.application_flags:#x}")
print(f"entry CS:IP seg{img.initial_cs}:{img.initial_ip:04X} SS:SP seg{img.initial_ss}:{img.initial_sp:04X} autoDS seg{img.auto_data_segment} heap {img.heap_size} stack {img.stack_size}")
print("modules", img.modules)
for s in img.segments:
    print(f" seg{s.number}: fileoff {s.file_offset:#x} len {len(s.data)} flags {s.flags:#06x} minalloc {s.minimum_allocation} relocs {len(s.relocations)} data={s.is_data}")
print("entry_points", img.entry_points)
print("resident", img.resident_exports)
print("nonresident", img.nonresident_exports[:20])

# imports grouped
by_mod = collections.Counter()
uniq = {}
for imp in img.imports:
    by_mod[imp.module]+=1
    uniq[(imp.module, imp.kind, imp.name, imp.ordinal)] = uniq.get((imp.module, imp.kind, imp.name, imp.ordinal),0)+1
print("import relocation records by module", dict(by_mod), "total records", len(img.imports))
print("unique imports", len(uniq))
for k,v in sorted(uniq.items()):
    print(" ", k, "x", v)

# analyze vs win30 and win31 api dirs
for label, apidir in [("win30", "/Users/macsd/winmine-hack/upstream/extract30/WINDOWS"),
                      ("win31", "/Users/macsd/winmine-hack/upstream/extract31/WINDOWS")]:
    res = analyze_bytes(data, str(winmine_path), pathlib.Path(apidir))
    cpu = res["cpu_analysis"]
    ctr = collections.Counter((i["mnemonic"], i["operands"]) for i in cpu["unsupported_instructions"])
    kindctr = collections.Counter()
    for i in cpu["unsupported_instructions"]:
        if i["mnemonic"]=="push": kindctr["push_imm"]+=1
        elif i["mnemonic"]=="imul": kindctr["imul_imm"]+=1
        elif i["mnemonic"] in ("shl","shr","sar","rol","ror","rcl","rcr","sal"): kindctr["shift_imm"]+=1
        else: kindctr[i["mnemonic"]]+=1
    print(f"\n== {label} verdict={res['verdict']} blockers={res['static_blockers']}")
    print(f" reachable={cpu['reachable_instruction_count']} code_bytes={cpu['code_bytes_reached']} unsupported={len(cpu['unsupported_instructions'])} kinds={dict(kindctr)}")
    print(f" decode_failures={len(cpu['decode_failures'])} uncertainties={len(cpu['instruction_classification_uncertainties'])} reloc_affected={len(cpu['relocation_affected_instructions'])} unresolved_edges={len(cpu['unresolved_control_flow'])}")
    print(" missing APIs:", res["api_reference"]["missing_3_0_apis"])
    # detailed unsupported list to file
    pathlib.Path(f"/Users/macsd/winmine-hack/artifacts/unsupported-{label}.json").write_text(json.dumps(cpu["unsupported_instructions"], indent=2))
    pathlib.Path(f"/Users/macsd/winmine-hack/artifacts/analysis-{label}.json").write_text(json.dumps(res, indent=2, default=str))

# exports of key modules in both windows versions
def dump_exports(root):
    rootp = pathlib.Path(root)
    for name in ["KERNEL.EXE","USER.EXE","GDI.EXE","SHELL.DLL","SOUND.DRV","WIN87EM.DLL","KRNL386.EXE"]:
        for p in sorted(rootp.rglob(name)):
            try:
                im = NEImage(p.read_bytes(), str(p))
            except Exception as e:
                print(root, name, "parse fail", e); continue
            byname, ords, complete = im.exports()
            print(f"{root} {p.relative_to(rootp)} size={p.stat().st_size} expWin={im.windows_version} progFlags={im.program_flags:#x} names={len(byname)} ords={sorted(ords)[:10]}... max={max(ords) if ords else None} complete={complete}")
            # save
            out = pathlib.Path("/Users/macsd/winmine-hack/artifacts") / f"exports-{pathlib.Path(root).name}-{p.stem}.json"
            out.write_text(json.dumps({"byname":byname,"ordinals":sorted(ords),"complete":complete}, indent=2))
for r in ["/Users/macsd/winmine-hack/upstream/extract30/WINDOWS","/Users/macsd/winmine-hack/upstream/extract31/WINDOWS"]:
    dump_exports(r)
