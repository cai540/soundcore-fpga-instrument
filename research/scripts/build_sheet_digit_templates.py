"""Create glyph-only OCR templates from OFL Noto fonts, without song images."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import hashlib,json,base64
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FONTS=ROOT/'build/sheet_acceptance_20261031/open_fonts'

def main():
    templates=[];sources=[]
    for source in sorted(FONTS.glob('*.ttf')):
        sources.append({'name':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'license':'SIL Open Font License 1.1'})
        for weight in (350,450,600,750,900):
            font=ImageFont.truetype(str(source),64);axes=font.get_variation_axes()
            font.set_variation_by_axes([weight if b'Weight' in a['name'] else a['default'] for a in axes])
            for digit in range(10):
                im=Image.new('L',(100,110),255);draw=ImageDraw.Draw(im);draw.text((12,0),str(digit),font=font,fill=0)
                box=Image.eval(im,lambda x:255-x).getbbox();pixels=features(im.crop(box))
                templates.append({'digit':digit,'font':source.stem,'weight':weight,'pixels':base64.b64encode(pixels).decode()})
    import matplotlib
    extra=Path(matplotlib.get_data_path())/'fonts/ttf'
    for name in ['DejaVuSans.ttf','DejaVuSans-Bold.ttf','DejaVuSerif.ttf','DejaVuSerif-Bold.ttf','STIXGeneral.ttf','STIXGeneralBol.ttf']:
        source=extra/name
        if not source.exists():continue
        sources.append({'name':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'license':'DejaVu or STIX font license bundled with Matplotlib'})
        for size in (24,48):
            for digit in range(10):
                im=Image.new('L',(100,110),255);ImageDraw.Draw(im).text((12,0),str(digit),font=ImageFont.truetype(str(source),size),fill=0)
                im=im.crop(Image.eval(im,lambda x:255-x).getbbox());templates.append({'digit':digit,'font':name,'weight':size,'pixels':base64.b64encode(features(im)).decode()})
    output={'version':2,'features':'area-average','width':12,'height':20,'source_fonts':sources,'templates':templates}
    destination=ROOT/'web/phone-lab-20261030/lib/digit-templates.json';destination.write_text(json.dumps(output,separators=(',',':')),encoding='utf8')
    license_file=ROOT/'web/phone-lab-20261030/lib/digit-templates-LICENSE.txt'
    license_file.write_text('\n\n'.join(p.read_text(encoding='utf8') for p in FONTS.glob('*OFL.txt')),encoding='utf8')
    print('glyph_templates',len(templates),'bytes',destination.stat().st_size)

def features(image):
    a=255-np.asarray(image,dtype=float);h,w=a.shape
    def weights(old,new):
        result=np.zeros((new,old))
        for i in range(new):
            start=i*old/new;end=(i+1)*old/new
            for j in range(int(start),min(old,int(np.ceil(end)))):result[i,j]=max(0,min(end,j+1)-max(start,j))/(end-start)
        return result
    return np.rint(weights(h,20)@a@weights(w,12).T).clip(0,255).astype('uint8').tobytes()

if __name__=='__main__':main()
