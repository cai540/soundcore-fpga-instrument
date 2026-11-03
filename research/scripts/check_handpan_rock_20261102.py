from pathlib import Path
import subprocess,json
R=Path(__file__).resolve().parents[1];B=R/'build/handpan_rock_20261102/tests';B.mkdir(parents=True,exist_ok=True)
BIN=Path('D:/FPGA/_Tools/iverilog-conda/Library/bin')
rtl=[str(p.relative_to(R))for p in (R/'rtl').glob('*.v')]
rows=[]
for short,top in [('modal','tb_handpan_modal32'),('fx','tb_rock_voice_fx'),('control','tb_handpan_control'),('core','tb_handpan_core'),('oled','tb_rock_oled')]:
    sources=[f'tb/{top}.v',*rtl]
    if short=='core':sources+=['board/pressure_i2s_additive32_core.v']
    binary=B/f'{short}.vvp'
    built=subprocess.run([str(BIN/'iverilog.exe'),'-g2012','-s',top,'-o',str(binary),*sources],cwd=R,capture_output=True,text=True)
    (B/f'{short}_compile.log').write_text(built.stdout+built.stderr,encoding='utf8')
    assert built.returncode==0,(short,built.stderr)
    ran=subprocess.run([str(BIN/'vvp.exe'),str(binary)],cwd=R,capture_output=True,text=True,timeout=180)
    (B/f'{short}.log').write_text(ran.stdout+ran.stderr,encoding='utf8');print(short,ran.stdout.strip(),flush=True)
    assert ran.returncode==0 and 'PASS' in ran.stdout,(short,ran.stdout,ran.stderr)
    rows.append(dict(name=top,passed=True))
(B/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
