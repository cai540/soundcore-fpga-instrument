"""Independent PNR option search using the exact same synthesized netlist."""
from pathlib import Path
import sys,shutil,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];B=R/'build/product_repair_20261103';N='soundcore_speaker_omr_60k'
place,route=map(int,sys.argv[1:3]);V=B/'pnr_alternatives'/f'place{place}_route{route}';V.mkdir(parents=True,exist_ok=True)
shutil.copytree(B/'src',V/'src',dirs_exist_ok=True)
shutil.copytree(B/'impl/gwsynthesis',V/'impl/gwsynthesis',dirs_exist_ok=True)
shutil.copy2(B/(N+'.gprj'),V/(N+'.gprj'))
config=dict(place_option=place,route_option=route,source_netlist_sha256=hashlib.sha256((B/'impl/gwsynthesis'/(N+'.vg')).read_bytes()).hexdigest(),code='B703')
(V/'variant.json').write_text(json.dumps(config,indent=2))
tcl=V/'run.tcl';tcl.write_text(f'open_project {{{(V/(N+".gprj")).as_posix()}}}\nset_option -user_code 0000B703\nset_option -place_option {place}\nset_option -route_option {route}\nrun pnr\n')
with (V/'build.log').open('w') as log:r=subprocess.run(['D:/FPGA/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe',str(tcl)],cwd=V,stdout=log,stderr=subprocess.STDOUT)
print(f'place{place}/route{route}: exit{r.returncode}',flush=True)
sys.exit(r.returncode)
