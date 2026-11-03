// Runtime service credentials only. No key may enter argv, logs, source or Site bundles.
import {readFileSync,writeFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const input=await new Promise((resolve,reject)=>{let text='';const tty=process.stdin.isTTY;
  const finish=()=>{process.stdin.pause();if(tty)process.stdin.setRawMode(false);resolve(text)};
  if(tty)process.stdin.setRawMode(true);process.stderr.write('Ready for private worker configuration on hidden stdin.\n');
  process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>{text+=chunk;if(text.length>20000||text.includes('\u0003'))reject(Error('Invalid private configuration'));else if(/[\r\n]/.test(text))finish()});process.stdin.once('end',finish);process.stdin.resume();
});
const config=JSON.parse(input),url=new URL(config.site_url);
if(url.protocol!=='https:'||!url.hostname.endsWith('.chatgpt.site')||url.pathname!=='/'||url.search||url.hash||typeof config.site_token!=='string'||config.site_token.length<24)throw Error('Invalid private service configuration');
const workerKey=readFileSync(new URL('../.score-api/web-worker.key',import.meta.url),'utf8').trim();
const destination=new URL('../.score-api/web-worker.json',import.meta.url);
writeFileSync(destination,JSON.stringify({site_url:url.origin,site_token:config.site_token,worker_key:workerKey,worker_id:randomUUID().replaceAll('-','')},null,2),{mode:0o600});
console.log('Private worker configuration saved outside source.');
