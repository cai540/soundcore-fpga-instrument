"""Read-only regression bridge: real provider transport, no keys in Node/output."""
from pathlib import Path
import json,sys,io,base64
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    command=json.load(sys.stdin)
    if command['op']=='digit_probe':
        import subprocess
        process=subprocess.run([sys.executable,__file__],input=json.dumps({'op':'contact','file':command['file'],'line':command['line']}),text=True,capture_output=True,encoding='utf8',check=True)
        image=json.loads(process.stdout)['detailImage']
        from score_api.bailian import completion
        from score_api.sheet import vision_config
        config=json.loads((ROOT/'config/score_api_bailian.json').read_text(encoding='utf8'))
        content=[{'type':'image_url','image_url':{'url':image}},{'type':'text','text':'这是一张符号网格。每格蓝色小字是编号，下面黑色大字是待识别内容。只读黑色形状，不做音乐分析。按蓝色编号升序返回JSON {"digits":[5,6,5,...]}。黑色图形若是0至7的单个数字就返回相应整数，若为括号、汉字、残片或无法辨清返回null。不要把1当竖线而删除。返回数量必须为'+str(len(command['line']['glyphs']))+'个。'}]
        result=completion({'model':'qwen3-vl-plus','enable_thinking':False,'temperature':0,'max_tokens':1000,'response_format':{'type':'json_object'},'messages':[{'role':'user','content':content}]},vision_config(config))
        print(result['content']);return
    if command['op'] in ('crop','indexed','contact'):
        from PIL import Image
        image=Image.open(command['file']).convert('RGB');line=command.get('line')
        if command['op']=='contact':
            from PIL import ImageDraw,ImageFont
            glyphs=line['glyphs'];columns=8;cell=100
            contact=Image.new('RGB',(columns*cell,((len(glyphs)+columns-1)//columns)*110),'white')
            draw=ImageDraw.Draw(contact);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
            for index,g in enumerate(glyphs):
                x=(index%columns)*cell;y=(index//columns)*110
                digit=image.crop((g['x'],g['y'],g['x']+g['w'],g['y']+g['h']))
                factor=min(64/digit.width,64/digit.height)
                digit=digit.resize((round(digit.width*factor),round(digit.height*factor)))
                contact.paste(digit,(x+(cell-digit.width)//2,y+30+(64-digit.height)//2))
                draw.text((x+cell//2,y+5),str(index+1),font=font,fill='#006ac6',anchor='mt')
            original=image.crop((0,max(0,line['cropTop']-12),image.width,min(image.height,line['cropBottom']+12)))
            scale=min(2,2600/image.width);original=original.resize((round(original.width*scale),round(original.height*scale)))
            result={}
            for key,im in [('image',original),('detailImage',contact)]:
                stream=io.BytesIO();im.save(stream,format='PNG');result[key]='data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()
            print(json.dumps(result));return
        if command['op']=='indexed':
            from PIL import ImageDraw,ImageFont
            scale=min(2,2600/image.width);strip=image.crop((0,line['cropTop'],image.width,line['cropBottom']))
            strip=strip.resize((round(strip.width*scale),round(strip.height*scale)))
            annotated=Image.new('RGB',(strip.width,strip.height+28),'white');annotated.paste(strip,(0,28));draw=ImageDraw.Draw(annotated)
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
            for g in line['glyphs']:
                x=g['x']*scale;y=(g['y']-line['cropTop'])*scale+28
                draw.rectangle((x-2,y-2,x+g['w']*scale+2,y+g['h']*scale+2),outline='#006ac6',width=1)
                draw.text((x+g['w']*scale/2,2),str(g['index']),font=font,fill='#006ac6',anchor='mt')
            original=image.crop((0,max(0,line['cropTop']-12),image.width,min(image.height,line['cropBottom']+12)))
            original=original.resize((round(original.width*scale),round(original.height*scale)))
            result={}
            for key,im in [('image',original),('detailImage',annotated)]:
                stream=io.BytesIO();im.save(stream,format='JPEG',quality=97);result[key]='data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode()
            print(json.dumps(result));return
        if line:
            top=max(0,int(line['top']*image.height/1000)-12);bottom=min(image.height,int(line['bottom']*image.height/1000+.999)+12)
            image=image.crop((0,top,image.width,bottom));scale=min(2,2600/image.width)
            image=image.resize((round(image.width*scale),round(image.height*scale)))
        stream=io.BytesIO();image.save(stream,format='JPEG',quality=97)
        print(json.dumps({'image':'data:image/jpeg;base64,'+base64.b64encode(stream.getvalue()).decode()}));return
    from score_api.bailian import completion
    from score_api.sheet import vision_config
    config=json.loads((ROOT/'config/score_api_bailian.json').read_text(encoding='utf8'))
    try:result=completion(command['payload'],vision_config(config))
    except Exception as error:
        if getattr(error,'code','').startswith('cloud_http_'):
            import re
            match=re.search(r'（([A-Za-z0-9_.-]{1,80})）',str(error))
            print(json.dumps({'_provider_error':{'status':int(error.code.rsplit('_',1)[1]),'code':match[1] if match else 'provider_http_error'}}));return
        raise
    print(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':result['content']}}],'usage':result['usage']},ensure_ascii=False))

if __name__=='__main__':main()
