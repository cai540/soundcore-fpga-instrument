"""Create separate headphone projects from the current product and known Dock pins."""
from pathlib import Path
import hashlib,json,re,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]; BOARD=ROOT/'board'; OUT=ROOT/'build/headphone_20261027'
OUT.mkdir(parents=True,exist_ok=True)

# Keep all external MAX projects buildable; selecting PT8211 is explicitly opt-in.
for path in BOARD.glob('*.gprj'):
    data=path.read_text(encoding='utf-8')
    if 'pressure_i2s_additive32_core.v' in data and 'pt8211_tx_12m288.v' not in data:
        backup=OUT/'before'/path.name
        if not backup.exists():shutil.copy2(path,backup)
        data=data.replace('    <FileList>','    <FileList>\n        <File path="../rtl/pt8211_tx_12m288.v" type="file.verilog" enable="1"/>')
        path.write_text(data,encoding='utf-8')

top=(BOARD/'pressure_i2s_panel_oled_ble_experiment_top.v').read_text()
ports=top[top.index('    input wire sys_clk,'):top.index('\n);')]
ports=ports.replace('dac_bclk','HP_BCK').replace('dac_lrclk','HP_WS').replace('dac_din','HP_DIN')
ports=ports.rstrip()+',\n    output wire PA_EN'
port_names=re.findall(r'(?:input|output|inout) wire (?:\[[^\]]+\] )?(\w+)',ports)
mapping={name: name for name in port_names if name!='PA_EN'}
for name,hp in [('dac_bclk','HP_BCK'),('dac_lrclk','HP_WS'),('dac_din','HP_DIN')]:
    del mapping[hp];mapping[name]=hp
connections=',\n'.join('        .'+name+'('+wire+')' for name,wire in mapping.items())
(BOARD/'soundcore_headphone_top.v').write_text(
    '// Current product, routed to the onboard headphone DAC. External MAX outputs are absent.\n'
    'module soundcore_headphone_top(\n'+ports+'\n);\n'
    '    pressure_i2s_panel_oled_ble_experiment_top #(.HEADPHONE_OUTPUT(1),.HEADPHONE_SHIFT(2)) product(\n'
    +connections+'\n    );\n    assign PA_EN=1\'b0;\nendmodule\n')

cst=(BOARD/'pressure_i2s_panel_oled_ble_experiment_60k.cst').read_text()
for old,new,ball in [('dac_bclk','HP_BCK','Y17'),('dac_lrclk','HP_WS','AB17'),('dac_din','HP_DIN','AA16')]:
    cst=cst.replace('"'+old+'"','"'+new+'"')
    cst=re.sub(r'IO_LOC "'+new+r'" \w+;',f'IO_LOC "{new}" {ball};',cst)
cst+='\n// Onboard headphone amplifier, active-low.\nIO_LOC "PA_EN" AB16;\nIO_PORT "PA_EN" IO_TYPE=LVCMOS33 PULL_MODE=NONE DRIVE=8 BANK_VCCIO=3.3;\n'
(BOARD/'soundcore_headphone_60k.cst').write_text(cst)

gprj=(BOARD/'pressure_i2s_panel_oled_ble_experiment_60k.gprj').read_text()
gprj=gprj.replace('pressure_i2s_panel_oled_ble_experiment_60k.cst','soundcore_headphone_60k.cst')
gprj=gprj.replace('    </FileList>','        <File path="soundcore_headphone_top.v" type="file.verilog" enable="1"/>\n    </FileList>')
(BOARD/'soundcore_headphone_60k.gprj').write_text(gprj)

# A second image needs no ADC/BLE/OLED/MAX or breadboard to test two onboard keys.
source_cst=(BOARD/'tang_mega_60k.cst').read_text()
check_cst='\n'.join(line for line in source_cst.splitlines() if line.startswith('IO_') and 'led_o' not in line)+'\n'
(BOARD/'headphone_check_60k.cst').write_text(check_cst)
files=['../rtl/instrument_texture.v','../rtl/synth_voice.v','../rtl/pt8211_tx_12m288.v',
       'audio_pll_12m288.v','headphone_check_top.v','headphone_check_60k.cst','tang_mega_60k.sdc']
check=ET.parse(BOARD/'pressure_i2s_panel_oled_ble_experiment_60k.gprj')
items=check.find('.//FileList');items.clear()
for name in files:
    kind='verilog' if name.endswith('.v') else name.rsplit('.',1)[1]
    ET.SubElement(items,'File',path=name,type='file.'+kind,enable='1')
ET.indent(check,space='    ')
check.write(BOARD/'headphone_check_60k.gprj',encoding='utf-8',xml_declaration=True)
for name,top_name in [('headphone_check','headphone_check_top'),('soundcore_headphone','soundcore_headphone_top')]:
    (BOARD/('build_'+name+'.tcl')).write_text(
        f'open_project D:/FPGA/Projects/soundcore_2026/board/{name}_60k.gprj\n'
        f'set_option -top_module {top_name}\nrun all\n')

# Use the current protected-file snapshot, never overwrite the original one.
shutil.copy2(ROOT/'build/quiet_texture_20261027/protected.json',OUT/'protected.json')
original=OUT/'before/pressure_i2s_panel_oled_ble_experiment_top.v'
print('Prepared 2 standalone build targets; no programmer invocation.')
