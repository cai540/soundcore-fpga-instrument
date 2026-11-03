/** Generic numbered-score runner: pixel geometry + actual FPGA classifier.
 * Header/complex repeat metadata remain explicit inputs/review, never guessed.
 */
import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
import {analyzeScorePixels,glyphsToRow} from '../web/phone-lab-20261030/lib/sheet-geometry.mjs';
import {joinSheetRows} from '../web/phone-lab-20261030/lib/sheet-symbols.mjs';
import {compileSheet} from '../web/phone-lab-20261030/lib/music.mjs';
const args=Object.fromEntries(process.argv.slice(2).map(a=>{const [k,...v]=a.replace(/^--/,'').split('=');return[k,v.join('=')||true]}));
if(!args.image||!args.out||[args.port,args.reference,args.export].filter(Boolean).length!==1)throw Error('Use --image=... --out=... with exactly one of --port=COMx, --reference, --export');
const root=path.resolve(import.meta.dirname,'..'),out=path.resolve(args.out);fs.mkdirSync(out,{recursive:true});
const model=path.resolve(args.model||path.join(root,'build/fpga_omr_20261031/model'));
const python=args.python||'python';
function run(argv){const p=spawnSync(python,argv,{cwd:root,encoding:'utf8',env:{...process.env,PYTHONIOENCODING:'utf-8'}});if(p.status!==0)throw Error(p.stderr||'FPGA request failed; no fallback used');return p.stdout;}
const image=path.resolve(args.image),rgba=path.join(out,'source.rgba');
const dimensions=JSON.parse(run(['-c','from PIL import Image;import sys,json;from pathlib import Path;im=Image.open(sys.argv[1]).convert("RGBA");Path(sys.argv[2]).write_bytes(im.tobytes());print(json.dumps(im.size))',image,rgba]));
const [width,height]=dimensions,geometry=analyzeScorePixels({width,height,data:fs.readFileSync(rgba)});
const job={image,glyphs:geometry.lines.flatMap((line,row)=>line.glyphs.map(g=>({row,index:g.index,box:[g.x,g.y,g.w,g.h]})))};
fs.writeFileSync(path.join(out,'job.json'),JSON.stringify(job));
const mode=args.port?['--port',String(args.port)]:[args.reference?'--reference':'--export'];
console.log(run(['-m','fpga_omr.batch','--job',path.join(out,'job.json'),'--model',model,'--output',path.join(out,'results.json'),...mode]).trim());
const results=JSON.parse(fs.readFileSync(path.join(out,'results.json'),'utf8'));
if(args.export)process.exit(0);
const [numerator,denominator]=String(args.meter||'4/4').split('/').map(Number);
const context={notation:'jianpu',title:String(args.title||'FPGA识谱待核对'),tonic_midi:Number(args.tonic||60),bpm:Number(args.bpm||80),numerator,denominator};
if(!Number.isInteger(context.tonic_midi)||context.tonic_midi<48||context.tonic_midi>72||context.bpm<30||context.bpm>240)throw Error('Invalid explicit key/BPM');
const rows=geometry.lines.map((line,row)=>{
 const symbols=results.glyphs.filter(g=>g.row===row);
 if(JSON.stringify(symbols.map(g=>g.box))!==JSON.stringify(line.glyphs.map(g=>[g.x,g.y,g.w,g.h])))throw Error('Hardware result crop identity mismatch');
 const unread=symbols.filter(g=>g.digit===null).map(g=>`本行${g.index}未确认为0至7：分类${g.class}`);
 return glyphsToRow(line,symbols.map(g=>g.digit),context,{unresolved:unread});
});
const score=joinSheetRows(context,rows);
score.unresolved=[...(score.unresolved||[]),'此入口未自动识别调号、速度、反复结构或中文歌词；请核对显式参数与演奏顺序。'];
fs.writeFileSync(path.join(out,'score.json'),JSON.stringify(score,null,2));
const compiled=compileSheet(score);fs.writeFileSync(path.join(out,'compiled.json'),JSON.stringify({...compiled,inference_location:results.inference_location},null,2));
console.log(JSON.stringify({location:results.inference_location,notes:compiled.events.filter(e=>e.midi!==null).length,review:compiled.review.status}));
