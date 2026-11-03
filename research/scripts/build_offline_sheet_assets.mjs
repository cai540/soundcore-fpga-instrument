import {build} from '../web/phone-lab-20261030/node_modules/esbuild/lib/main.js';
import {cp,mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..'),site=resolve(root,'web/phone-lab-20261030'),assets=resolve(root,'app/android/app/src/main/assets/offline');
await mkdir(assets,{recursive:true});
await cp(resolve(site,'public/offline/ocr'),resolve(assets,'ocr'),{recursive:true});
await build({entryPoints:[resolve(site,'lib/native-offline-entry.mjs')],outfile:resolve(assets,'engine.js'),bundle:true,format:'iife',platform:'browser',target:'chrome100',minify:true,legalComments:'eof'});
await writeFile(resolve(assets,'index.html'),'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Soundcore local score engine</title><script src="engine.js"></script>');
const manifest={source:'bundled local OCR + phone int8 symbol model; explicit optional FPGA inference',files:{}};
async function walk(dir){for(const item of await readdir(dir,{withFileTypes:true})){const path=resolve(dir,item.name);if(item.isDirectory())await walk(path);else if(item.name!=='manifest.json'){const bytes=await readFile(path);manifest.files[path.slice(assets.length+1).replaceAll('\\','/')]={bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')};}}}
await walk(assets);await writeFile(resolve(assets,'manifest.json'),JSON.stringify(manifest,null,2));console.log(JSON.stringify({files:Object.keys(manifest.files).length,bytes:Object.values(manifest.files).reduce((s,f)=>s+f.bytes,0)}));
