"""Parametric assembly study, not a reverse-engineered manufactured product.

Run in isolated cadquery_env. All provisional dimensions live in parameters.json.
No physical PCB drilling pattern is inferred from a single photograph.
"""
from pathlib import Path
import json,math
import cadquery as cq
import vtk
from PIL import Image,ImageDraw,ImageFont
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/engineering_upgrade_20261028/cad'
OUT.mkdir(parents=True,exist_ok=True)
FONT=FontProperties(fname=r'C:\Windows\Fonts\msyh.ttc')
P={'width':420,'depth':240,'height':80,'panel_thickness':3,'wall_thickness':3,
   'pad_width':34,'pad_depth':34,'pad_height':7,'button_small_hole':12,'button_large_hole':16,
   'oled_window_width':23,'oled_window_height':13,'slider_slot_width':4,'slider_slot_length':54,
   'rotary_hole':7.5,'led_lightpipe_hole':3,
   'status':'规划尺寸，未按实物测量；不得直接加工',
   'confidence':{'enclosure':'design assumption','pad':'existing part envelope placeholder',
      'module_envelopes':'clearance placeholders, not measured PCB outlines',
      'buttons':'12/16mm prior purchase plan; verify received hardware',
      'oled_window':'nominal display allowance; verify actual bezel',
      'fastener_holes':'M3 design assumption; not original board mounting holes'}}
param_path=OUT/'parameters.json'
if param_path.exists():
    old=json.loads(param_path.read_text(encoding='utf-8'))
    P.update(old)
else:param_path.write_text(json.dumps(P,ensure_ascii=False,indent=2),encoding='utf-8')
W,D,H,T=P['width'],P['depth'],P['height'],P['panel_thickness']
parts=[]

def add(name,shape,color,group='inside',desc=''):
    if isinstance(shape,cq.Workplane):shape=shape.val()
    assert shape.isValid(),name
    parts.append({'name':name,'shape':shape,'color':color,'group':group,'description':desc})

def cuboid(w,d,h,x,y,z):return cq.Workplane('XY').box(w,d,h).translate((x,y,z+h/2))

def cyl(r,h,x,y,z):return cq.Workplane('XY').circle(r).extrude(h).translate((x,y,z))

pad_centers=[(-165+40*i,25+36*math.sin(i*math.pi/6)) for i in range(7)]
buttons=[('K1',125,-63,12),('K2',160,-63,12),('K3',125,-96,12),('K4',160,-96,12),('K5',190,-80,16)]
base=cuboid(W,D,T,0,0,0)
add('base_plate',base,(.23,.25,.27),'base','底板；设计尺寸')
top=cuboid(W,D,T,0,0,H-T)
top=top.cut(cuboid(P['oled_window_width'],P['oled_window_height'],T+4,150,78,H-T-2))
top=top.cut(cuboid(P['slider_slot_width'],P['slider_slot_length'],T+4,125,0,H-T-2))
top=top.cut(cyl(P['rotary_hole']/2,T+4,174,0,H-T-2))
for _,x,y,diam in buttons:top=top.cut(cyl(diam/2,T+4,x,y,H-T-2))
for x,y in pad_centers:top=top.cut(cyl(P['led_lightpipe_hole']/2,T+4,x,y-24,H-T-2))
for x in [-W/2+12,W/2-12]:
    for y in [-D/2+12,D/2-12]:top=top.cut(cyl(1.6,T+4,x,y,H-T-2))
add('top_panel',top,(.13,.15,.17),'top','不透明上面板；开孔参数待实测')
for name,w,d,x,y in [('front_wall',W,T,0,-D/2+T/2),('rear_wall',W,T,0,D/2-T/2),
                      ('left_wall',T,D-2*T,-W/2+T/2,0),('right_wall',T,D-2*T,W/2-T/2,0)]:
    wall=cuboid(w,d,H-2*T,x,y,T)
    if name=='rear_wall':
        # Single product power inlet: provisional 12mm panel opening.
        hole=cq.Workplane('XZ').center(170,24).circle(6).extrude(T+6,both=True).translate((0,D/2-T/2,0))
        wall=wall.cut(hole)
    if name=='front_wall':
        # Speaker vent slots only; actual speaker basket not inferred.
        for dx in range(-24,25,6):
            cutter=cq.Workplane('XZ').center(-150+dx,34).rect(2,32-abs(dx)*.4).extrude(T+6,both=True).translate((0,-D/2+T/2,0))
            wall=wall.cut(cutter)
    add(name,wall,(.31,.33,.35),'walls','侧板；接口需按实物定孔')
for x in [-W/2+12,W/2-12]:
    for y in [-D/2+12,D/2-12]:
        st=cyl(4,H-2*T,x,y,T).cut(cyl(1.6,H-2*T+2,x,y,T-1))
        add(f'standoff_{x}_{y}',st,(.7,.7,.72),'inside','M3机身支柱设计占位')
for i,(x,y) in enumerate(pad_centers):
    pad=cuboid(P['pad_width'],P['pad_depth'],P['pad_height'],x,y,H)
    pad=pad.edges('|Z').fillet(3)
    add(f'existing_pad_{i+1}',pad,(.67,.69,.71),'controls','已有敲击面的外包络占位')
    add(f'led_lightpipe_{i+1}',cyl(1.45,T+2,x,y-24,H-T),(.45,.80,.76),'controls','导光点；非RGB')
oledpcb=cuboid(27,27,1.6,150,78,H-T-5)
add('oled_board',oledpcb,(.08,.38,.27),'controls','OLED模块外包络近似')
add('oled_screen',cuboid(21.7,10.9,1,150,78,H-.4),(.10,.48,.53),'controls','显示区域名义占位')
add('slider_body',cuboid(12,70,12,125,0,H-T-14),(.40,.42,.44),'controls')
add('slider_cap',cuboid(16,10,6,125,0,H),(.65,.66,.67),'controls')
add('rotary_shaft',cyl(3.5,10,174,0,H-3),(.70,.71,.72),'controls')
add('rotary_knob',cyl(11,13,174,0,H+3),(.27,.28,.30),'controls')
for name,x,y,diam in buttons:
    add(name+'_body',cyl(diam/2-1,22,x,y,H-T-22),(.52,.53,.55),'controls')
    add(name+'_cap',cyl(diam/2+1,3,x,y,H),(.70,.72,.73) if name!='K5' else (.35,.67,.61),'controls')

module_specs=[('fpga_dock_envelope',155,90,40,-52,-20,10,'FPGA底板及散热器，包络待实测'),
 ('adc_module_envelope',55,35,15,68,-22,12,'ADC模块，尺寸待实测'),
 ('buck_module_envelope',50,28,20,142,-65,9,'新电源模块，型号/尺寸待核对'),
 ('jdy_module_envelope',44,27,13,156,35,12,'蓝牙模块与天线净空占位'),
 ('max_module_envelope',31,25,13,-155,-63,11,'MAX功放，尺寸待核对')]
for name,w,d,h,x,y,z,desc in module_specs:
    add(name+'_pcb',cuboid(w,d,1.6,x,y,z),(.08,.35,.22),'inside',desc)
    add(name+'_clearance',cuboid(w*.78,d*.76,h-1.6,x,y,z+1.6),(.33,.35,.37),'inside','安装净空体，不代表内部元件几何')

assembly=cq.Assembly(name='Soundcore_planning_assembly')
for a in parts:assembly.add(a['shape'],name=a['name'],color=cq.Color(*a['color']))
step=OUT/'声芯_装配规划模型_待实测.step'
assembly.export(str(step),exportType='STEP')
compound=cq.Compound.makeCompound([a['shape'] for a in parts])
cq.exporters.export(compound,str(OUT/'声芯_装配规划模型_待实测.stl'),tolerance=.3,angularTolerance=.2)
try:assembly.export(str(OUT/'声芯_装配规划模型_待实测.glb'),exportType='GLTF')
except Exception as e:(OUT/'gltf_note.txt').write_text(str(e),encoding='utf-8')

def mesh_for(a):
    vs,ts=a['shape'].tessellate(.8,.25)
    v=np.asarray([x.toTuple() for x in vs]);t=np.asarray(ts,dtype=int)
    return v,t

meshes=[mesh_for(a) for a in parts]
def render(name,mode='assembled',elev=27,azim=-62):
    ren=vtk.vtkRenderer();ren.SetBackground(1,1,1)
    for a,(v,t) in zip(parts,meshes):
        v=v.copy()
        if mode=='exploded':
            v[:,2]+=95 if a['group']=='controls' else 68 if a['group']=='top' else 0
            if a['group']=='walls':v[:,2]+=10
        elif mode=='inside' and (a['group'] in ['top','controls'] or a['name'] in ['front_wall','right_wall']):continue
        points=vtk.vtkPoints()
        for xyz in v:points.InsertNextPoint(*xyz)
        cells=vtk.vtkCellArray()
        for tri in t:
            cells.InsertNextCell(3)
            for idx in tri:cells.InsertCellPoint(int(idx))
        mesh=vtk.vtkPolyData();mesh.SetPoints(points);mesh.SetPolys(cells)
        norm=vtk.vtkPolyDataNormals();norm.SetInputData(mesh);norm.SplittingOn();norm.SetFeatureAngle(40)
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(norm.GetOutputPort())
        actor=vtk.vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetColor(*a['color'])
        actor.GetProperty().SetAmbient(.30);actor.GetProperty().SetDiffuse(.70);actor.GetProperty().SetSpecular(.12)
        ren.AddActor(actor)
    zfocus=105 if mode=='exploded' else 42
    cam=ren.GetActiveCamera();cam.SetPosition(510,-790,710 if mode=='inside' else 560)
    cam.SetFocalPoint(0,0,zfocus);cam.SetViewUp(0,0,1);cam.ParallelProjectionOn();cam.SetParallelScale(230 if mode=='exploded' else 200)
    ren.ResetCameraClippingRange()
    rw=vtk.vtkRenderWindow();rw.SetOffScreenRendering(1);rw.SetSize(1800,1100);rw.SetMultiSamples(8);rw.AddRenderer(ren);rw.Render()
    capture=vtk.vtkWindowToImageFilter();capture.SetInput(rw);capture.ReadFrontBufferOff();capture.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/name));writer.SetInputConnection(capture.GetOutputPort());writer.Write();rw.Finalize()
    im=Image.open(OUT/name).convert('RGB');d=ImageDraw.Draw(im)
    if mode=='inside':
        tags=[('max_module_envelope_clearance','MAX功放包络',(180,850)),
              ('fpga_dock_envelope_clearance','FPGA与散热净空',(535,925)),
              ('adc_module_envelope_clearance','ADC模块包络',(900,945)),
              ('buck_module_envelope_clearance','已购电源包络',(1265,925)),
              ('jdy_module_envelope_clearance','蓝牙与天线净空',(1610,850))]
        ft=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',23)
        for key,caption,(tx,ty) in tags:
            shape=next(x['shape'] for x in parts if x['name']==key);bb=shape.BoundingBox()
            co=vtk.vtkCoordinate();co.SetCoordinateSystemToWorld();co.SetValue((bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,bb.zmax)
            sx,sy=co.GetComputedDisplayValue(ren);sy=1100-sy
            d.line([(tx,ty-16),(tx,ty-44),(sx,sy)],fill='#333333',width=2)
            d.ellipse((sx-4,sy-4,sx+4,sy+4),fill='#333333')
            bounds=d.textbbox((tx,ty),caption,font=ft,anchor='mm');bounds=(bounds[0]-9,bounds[1]-6,bounds[2]+9,bounds[3]+6)
            d.rectangle(bounds,fill='white',outline='#555555',width=1);d.text((tx,ty),caption,font=ft,fill='black',anchor='mm')
    title={'assembled':'三维装配规划 · 俯视透视','exploded':'三维装配规划 · 分解视图','inside':'三维装配规划 · 内部净空（移除前、右侧板）'}[mode]
    d.text((900,36),title,font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',34),anchor='mt',fill='black')
    d.text((900,1050),'参数化CAD；尺寸为设计占位，未按实物测量，不作为加工定稿',font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',24),anchor='mt',fill='black')
    im.save(OUT/name)
render('assembly.png')
render('exploded.png','exploded',25,-63)
render('inside.png','inside',55,-62)

# Reload STEP to verify it is actual valid geometry rather than only an image.
restored=cq.importers.importStep(str(step)).val()
check={'parts':len(parts),'valid_before_export':all(a['shape'].isValid() for a in parts),
       'step_reimport_valid':restored.isValid(),'step_solid_count':len(restored.Solids()),
       'step_bytes':step.stat().st_size,'dimensions_are_provisional':True,
       'photo_reconstruction_performed':False,
       'parts_list':[{'name':a['name'],'group':a['group'],'description':a['description']} for a in parts]}
(OUT/'cad_validation.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in check.items() if k!='parts_list'},ensure_ascii=False,indent=2))
