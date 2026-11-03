"""Generate probe-tip/common-ground guides without inventing FPGA pin numbers."""
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/acceptance_20261102/previews'

def draw(name,title,subtitle,rows,warning):
    width=1100; height=650
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1100" height="650" fill="#fff"/>',
        '<style>text{font-family:"Microsoft YaHei",sans-serif;fill:#193541}.h{font-size:28px;font-weight:700}.s{font-size:18px}.label{font-size:22px}.small{font-size:17px}.wire{stroke:#087c70;stroke-width:4;fill:none}</style>',
        f'<text class="h" x="40" y="55">{escape(title)}</text>',
        f'<text class="s" x="40" y="91">{escape(subtitle)}</text>',
        '<rect x="40" y="125" width="360" height="330" rx="16" fill="#f0f6f6" stroke="#b7ced0"/>',
        '<rect x="740" y="125" width="320" height="330" rx="16" fill="#f0f6f6" stroke="#b7ced0"/>',
        '<text class="label" x="64" y="161">产品模块上的信号</text>',
        '<text class="label" x="764" y="161">示波器探头尖端</text>']
    for i,(source,target) in enumerate(rows):
        y=215+i*65
        parts += [f'<text class="label" x="64" y="{y+7}">{escape(source)}</text>',
            f'<circle cx="400" cy="{y}" r="6" fill="#087c70"/>',
            f'<path class="wire" d="M406 {y} H720"/><path d="M708 {y-7} L724 {y} L708 {y+7}" fill="#087c70"/>',
            f'<text class="label" x="764" y="{y+7}">{escape(target)}</text>']
    parts += ['<path d="M220 455 V495 H900 V455 M560 495 V512 M540 512 H580 M547 521 H573 M554 530 H566" stroke="#283b43" stroke-width="3" fill="none"/>',
        '<text class="label" x="40" y="562">全部普通探头地夹 → 系统公共 GND</text>',
        '<text class="small" x="40" y="590">ADC、FPGA、MAX 与系统电源的公共地；关电固定探头，使用10X并核对衰减设置。</text>',
        f'<text class="s" x="40" y="626" style="fill:#ad251c;font-weight:700">{escape(warning)}</text>', '</svg>']
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text('\n'.join(parts),encoding='utf8')

draw('示波器_数字链路接线.svg','A · 压力输入 → FPGA实际 I2S 音频',
     '四通道同时采集：压力信号 + 位时钟 + 声道时钟 + 数据。',
     [('ADC AIx 压力信号','CH1'),('MAX BCLK','CH2'),('MAX LRC / LRCLK','CH3'),('MAX DIN','CH4')],
     'CH1接压力分压中点；不要接3.3V供电端。数字信号原始采样率建议≥25MSa/s。')
draw('示波器_功放差分接线.svg','B · 压力输入 → MAX功放差分音频',
     '无差分探头时：两根普通探头分别对公共地测输出，数学通道 CH2−CH3。',
     [('ADC AIx 压力信号','CH1'),('MAX SPK+ / OUT+','CH2'),('MAX SPK− / OUT−','CH3')],
     'SPK−不是GND，不能接普通探头地夹！差分波形需低通去除Class-D开关载波。')
print('Written two explicit probe-tip/common-ground SVG guides')
