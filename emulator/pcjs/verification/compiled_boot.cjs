// MIT. Run the exact delivered compiled bundle in Node, NOT browser DOM/input QA.
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const [fixtureArg, outArg] = process.argv.slice(2);
if (!fixtureArg || !outArg) throw Error('Usage: node compiled_boot.cjs FIXTURE OUTPUT');
const fixture = path.resolve(fixtureArg), out = path.resolve(outArg);
const sha = b => createHash('sha256').update(b).digest('hex');
const assets = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'assets.json')));
for (const asset of assets.assets) {
  if (sha(fs.readFileSync(path.join(fixture, 'vendor', asset.name))) !== asset.sha256) throw Error('Asset mismatch: '+asset.name);
}
const disk = fs.readFileSync(path.join(fixture, 'disk.json'), 'utf8');
global.resources = {parms: '{}', 'disk.json': disk};
for (const name of ['ATBIOS-REV3.json5', 'IBM-EGA.json5']) global.resources['vendor/'+name] = fs.readFileSync(path.join(fixture, 'vendor', name), 'utf8');
require(path.join(fixture, 'vendor', 'pcx86.js'));
const machine = {
  machine: {id:'judge286',type:'pcx86'}, computer:{id:'computer',buswidth:24,resume:0},
  ram:[{id:'ramLow',addr:0,size:0xa0000,test:false}],
  rom:[{id:'romBIOS',addr:0xf0000,size:0x10000,alias:0xff0000,file:'vendor/ATBIOS-REV3.json5'},
       {id:'romEGA',addr:0xc0000,size:0x4000,file:'vendor/IBM-EGA.json5',notify:'videoEGA'}],
  video:[{id:'videoEGA',model:'ega',memory:0x20000,screenWidth:1280,screenHeight:700}],
  fdc:{id:'fdc'},hdc:{id:'hdc',type:'AT',drives:[{name:'judge disk',type:2,path:'disk.json'}]},
  keyboard:{id:'keyboard',model:'US84'},cpu:{id:'cpu',model:80286,cycles:8000000,multiplier:1,autoStart:true},
  chipset:{id:'chipset',model:5170,floppies:[1200,1200]},serial:{id:'com1',adapter:1},mouse:{id:'mouse',serial:'com1'}
};
embedPCx86('judge286', null, null, JSON.stringify(machine));
sendEvent('init');
const cpu = PCjs.components.find(c => c.type === 'CPU');
const video = PCjs.components.find(c => c.type === 'Video');
if (!cpu || !video) throw Error('Compiled components did not initialize');
// Decode PCjs State's documented alternating even/odd count-value format.
function decompress(encoded, length) {
  if (encoded.length === length) return encoded;
  const result = Array(length).fill(0); let position=0, written=0;
  if (encoded.length % 2) throw Error('Invalid RLE');
  for (let i=0;i<encoded.length;i+=2) {
    const count=encoded[i],value=encoded[i+1];
    if (!Number.isSafeInteger(count) || count<1 || written+count>length) throw Error('Invalid RLE count');
    for (let n=0;n<count;n++) { if(position>=length) throw Error('RLE overflow');result[position]=value;position+=2;written++; }
    if (position===length) position=1;
  }
  if(written!==length) throw Error('Incomplete RLE');
  return result;
}
setTimeout(() => {
  const state=video.save(), card=state[3], ega=card[6], registers=cpu.save();
  const msw=registers[1][5][0];
  fs.mkdirSync(out,{recursive:true});
  fs.writeFileSync(path.join(out,'compiled-ega.json'),JSON.stringify({memory:decompress(ega[14],card[8]),atc:ega[2],crtc:card[5],videoMode:state[2][2]}));
  const report={sourceDiskSha256:sha(disk),sourceDiskUnchanged:sha(fs.readFileSync(path.join(fixture,'disk.json')))===sha(disk),bundleSha256:sha(fs.readFileSync(path.join(fixture,'vendor','pcx86.js'))),cpu:80286,clockMultiplier:1,msw,protectedMode:!!(msw&1),videoMode:state[2][2],qualification:'Exact compiled bundle in Node using PCjs resource-cache and JSON initialization. Saved EGA state, not browser DOM/input QA. Inspect rendered frame; process exit alone is not a game pass.'};
  fs.writeFileSync(path.join(out,'compiled-report.json'),JSON.stringify(report,null,2));
  console.log(report);process.exit(0);
},15000);
