"""Explicit hardware / CPU-reference / export modes; never silently substitute an API."""
from pathlib import Path
import argparse,json,sys,time
import numpy as np
from PIL import Image
from .model import normalize,pack_pixels,load_weights,integer_forward,classify
from .protocol import HardwareModel

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--model',type=Path,required=True)
    mode=ap.add_mutually_exclusive_group(required=True);mode.add_argument('--port');mode.add_argument('--reference',action='store_true');mode.add_argument('--export',action='store_true')
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--baud',type=int,default=9600);args=ap.parse_args()
    job=json.loads(args.job.read_text(encoding='utf8'));manifest=json.loads((args.model/'manifest.json').read_text(encoding='utf8'))
    im=Image.open(job['image']).convert('L');features=[]
    for glyph in job['glyphs']:
        x,y,w,h=glyph['box']
        if not(0<=x<x+w<=im.width and 0<=y<y+h<=im.height):raise ValueError('Crop outside image')
        features.append(normalize(im.crop((x,y,x+w,y+h))))
    transport=None;start=time.monotonic()
    try:
        if args.port:
            import serial
            transport=serial.Serial(args.port,args.baud,timeout=.05,write_timeout=2)
            hardware=HardwareModel(transport,manifest['model_crc32']);records=[hardware.predict(x)for x in features];location='fpga'
        elif args.reference:
            scores=integer_forward(np.asarray(features),load_weights(args.model));digits,margins=classify(scores)
            records=[{'digit':int(d)if d<=7 else None,'class':int(d),'margin':int(m)}for d,m in zip(digits,margins)];location='cpu_reference'
        else:
            records=[{'bitmap_hex':pack_pixels(x).hex()}for x in features];location='not_inferred'
        result={'schema_version':1,'model_crc32':manifest['model_crc32'],'inference_location':location,'seconds':round(time.monotonic()-start,3),
                'glyphs':[{**g,**r}for g,r in zip(job['glyphs'],records)]}
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'location':location,'glyphs':len(records),'seconds':result['seconds']}))
    finally:
        if transport is not None:transport.close()

if __name__=='__main__':main()
