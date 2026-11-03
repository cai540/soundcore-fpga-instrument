from pathlib import Path
import json,argparse
import pythoncom,win32com.client
import fitz
from PIL import Image,ImageDraw

parser=argparse.ArgumentParser();parser.add_argument('--shared-pitch',action='store_true');args=parser.parse_args()
if args.shared_pitch:
    ROOT=Path(__file__).resolve().parents[1]/'output/shared_pitch_20261028'
    targets=[ROOT/'report/声芯_竞赛技术文档_共享流水线实证版.docx',ROOT/'results/共享音高流水线_优化结果.docx']
else:
    ROOT=Path(__file__).resolve().parents[1]/'output/engineering_upgrade_20261028'
    targets=[ROOT/'report/声芯_竞赛技术文档_工程图修订版.docx',ROOT/'proposal/声芯_技术创新与资源优化方案.docx']
pythoncom.CoInitialize();word=win32com.client.DispatchEx('Word.Application');word.Visible=False;word.DisplayAlerts=0
try:
 for path in targets:
    doc=None
    try:
        doc=word.Documents.Open(str(path),ConfirmConversions=False,ReadOnly=True,AddToRecentFiles=False)
        doc.Fields.Update();doc.Repaginate();pages=doc.ComputeStatistics(2)
        doc.ExportAsFixedFormat(str(path.with_suffix('.pdf')),17,OpenAfterExport=False,OptimizeFor=0)
    finally:
        if doc is not None:doc.Close(False)
    out=path.parent/'rendered';out.mkdir(exist_ok=True)
    summaries=[];thumbs=[];overflow=[]
    with fitz.open(path.with_suffix('.pdf')) as f:
        for i,page in enumerate(f):
            page.get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False).save(out/f'page-{i+1:02d}.png')
            pix=page.get_pixmap(matrix=fitz.Matrix(.48,.48),alpha=False)
            im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
            tile=Image.new('RGB',(im.width+12,im.height+35),'#e8e8e8');tile.paste(im,(6,27))
            ImageDraw.Draw(tile).text((8,6),f'Page {i+1}',fill='black');thumbs.append(tile)
            txt=page.get_text();summaries.append({'page':i+1,'chars':len(txt),'start':txt[:80],'end':txt[-100:]})
            for block in page.get_text('dict')['blocks']:
                if block['type']!=0:continue
                for line in block['lines']:
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        if x0 < 15 or x1 > page.rect.width-15 or y0<8 or y1>page.rect.height-8:
                            overflow.append({'page':i+1,'text':span['text'],'bbox':span['bbox']})
        cols=3;rows=(len(thumbs)+2)//3;cw=max(x.width for x in thumbs);ch=max(x.height for x in thumbs)
        sheet=Image.new('RGB',(cols*cw,rows*ch),'#ccc')
        for i,t in enumerate(thumbs):sheet.paste(t,((i%cols)*cw,(i//cols)*ch))
        sheet.save(out/'contact_sheet.png')
        (path.parent/'pdf_text.txt').write_text('\n\n'.join(p.get_text() for p in f),encoding='utf-8')
        result={'word_pages':pages,'pdf_pages':len(f),'overflow':overflow,'pages':summaries}
        (path.parent/'render_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'file':path.name,'pages':len(f),'overflow':len(overflow)},ensure_ascii=False),flush=True)
finally:word.Quit();pythoncom.CoUninitialize()
