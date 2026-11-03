// Compare exact official PCjs EGA renderer against our captured-VRAM formula.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const [runtimeArg,snapshot]=process.argv.slice(2);
if(!runtimeArg||!snapshot)throw Error('Usage: node renderer_parity.mjs RUNTIME SNAPSHOT');
const runtime=path.resolve(runtimeArg);
const lock=JSON.parse(fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)),'runtime-lock.json')));
for(const [name,sha] of Object.entries(lock.sha256))if(createHash('sha256').update(fs.readFileSync(path.join(runtime,name))).digest('hex')!==sha)throw Error('Runtime hash mismatch: '+name);
const {default:Video}=await import(pathToFileURL(path.join(runtime,'machines/pcx86/modules/v2/video.js')));
const j=JSON.parse(fs.readFileSync(snapshot));
if(j.atc[19]!==0||j.crtc[12]!==0||j.crtc[13]!==0||j.crtc[19]!==40)throw Error('Only reference mode10h display layout supported');
const v=Object.create(Video.prototype);
v.cardEGA=v.cardColor=v.cardActive={regATCData:j.atc,adwMemory:j.memory};
v.aRGB=[];v.fRGBValid=false;v.nCols=v.nColsLogical=640;v.nRows=350;v.aCellCache=new Array(28000);v.iCellCacheValid=0;
v.imageBuffer={width:640,height:350,data:new Uint8ClampedArray(640*350*4)};
v.contextBuffer={putImageData(){}};v.contextScreen={drawImage(){}};
v.updateScreenGraphicsEGA(0,0,28000);
let differences=0;
for(let y=0;y<350;y++)for(let x=0;x<640;x++){
  const d=j.memory[y*80+(x>>3)]||0,b=7-(x&7);let n=0;
  for(let p=0;p<4;p++)n|=((d>>>(8*p+b))&1)<<p;
  const c=j.atc[n],rgb=[2,1,0].map(q=>170*((c>>q)&1)+85*((c>>(q+3))&1));
  const offset=(y*640+x)*4;
  for(let q=0;q<3;q++)if(rgb[q]!==v.imageBuffer.data[offset+q])differences++;
}
console.log(JSON.stringify({pixels:640*350,channelDifferences:differences,atcHorizontalPanning:j.atc[19],officialPalette:v.aRGB},null,2));
if(differences)process.exitCode=1;
