// Optional diagnostic harness: official PCjs source core, not browser QA.
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const [runtimeArg, fixtureArg, outputArg, mode='bridge']=process.argv.slice(2);
if(!runtimeArg||!fixtureArg||!outputArg||!['bridge','control','gameplay','failure','timing'].includes(mode))throw Error('Usage: node headless.mjs RUNTIME FIXTURE OUTPUT [bridge|control|gameplay|failure|timing]');
const runtime=path.resolve(runtimeArg),base=path.resolve(fixtureArg),out=path.resolve(outputArg);
fs.mkdirSync(out,{recursive:true});
const sourceDiskSha256=createHash('sha256').update(fs.readFileSync(path.join(base,'disk.json'))).digest('hex');
const moduleURL=p=>pathToFileURL(path.join(runtime,p)).href;
const lock=JSON.parse(fs.readFileSync(path.join(here,'runtime-lock.json')));
for(const p of Object.keys(lock.sha256)){if(createHash('sha256').update(fs.readFileSync(path.join(runtime,p))).digest('hex')!==lock.sha256[p])throw Error('Runtime integrity mismatch: '+p);}
const {globals}=await import(moduleURL('machines/modules/v2/defines.js'));
const {default:Component}=await import(moduleURL('machines/modules/v2/component.js'));
const {default:Web}=await import(moduleURL('machines/modules/v2/weblib.js'));
const {embedPCx86}=await import(moduleURL('machines/modules/v2/embed.js'));
globals.browser=false;
let diskSha256=null;let controlDisk=null;if(mode==='control'||mode==='failure'){controlDisk=execFileSync('python3',[path.join(here,'control.py'),path.join(base,'disk.json'),mode],{maxBuffer:32*1024*1024}).toString();}
globals.node.readFileSync=(p,e)=>{const data=controlDisk&&p.endsWith('/disk.json')?controlDisk:fs.readFileSync(p,e);if(p.endsWith('/disk.json')){diskSha256=createHash('sha256').update(data).digest('hex');console.log('DISK_SHA256',diskSha256);}return data;};
for (const p of lock.modules) await import(moduleURL(p));
const prefix=path.join(out,mode);
const machine={
 machine:{id:'judge286',type:'pcx86'},
 computer:{id:'computer',buswidth:24,resume:0},
 ram:[{id:'ramLow',addr:0,size:0xa0000,test:false}],
 rom:[{id:'romBIOS',addr:0xf0000,size:0x10000,alias:0xff0000,file:base+'/vendor/ATBIOS-REV3.json5'},
 {id:'romEGA',addr:0xc0000,size:0x4000,file:base+'/vendor/IBM-EGA.json5',notify:'videoEGA'}],
 video:[{id:'videoEGA',model:'ega',memory:0x20000,screenWidth:1280,screenHeight:700}],
 fdc:{id:'fdc'},hdc:{id:'hdc',type:'AT',drives:[{name:'judge disk',type:2,path:base+'/disk.json'}]},
 keyboard:{id:'keyboard',model:'US84'},cpu:{id:'cpu',model:80286,cycles:8000000,multiplier:1,autoStart:false},
 chipset:{id:'chipset',model:5170,floppies:[1200,1200]},serial:{id:'com1',adapter:1},mouse:{id:'mouse',serial:'com1'},
 debugger:{id:'debugger'}
};
embedPCx86('judge286',null,null,JSON.stringify(machine));Web.doPageInit();
const cpu=Component.getComponentByType('CPU');
console.log('CPU component',!!cpu);
let output='';let f8=0;cpu.addIntNotify(0xf8,()=>{f8++;return true});const bus=cpu.bus;const video=Component.getComponentByType('Video');
cpu.addIntNotify(0x10,()=>{let ah=(cpu.regEAX>>8)&255;if(ah===14){let s=String.fromCharCode(cpu.regEAX&255);output+=s;process.stdout.write(s)} return true});
const kbd=Component.getComponentByType('Keyboard');
setTimeout(()=>cpu.startCPU(),200);
setInterval(()=>{console.log('\nSTATE',JSON.stringify({cycles:cpu.getCycles(),cs:cpu.segCS.sel,ip:cpu.getIP(),msw:cpu.regCR0,ax:cpu.regEAX,run:cpu.isRunning()}));},10000);

function snap(tag){let v=video.cardEGA;let ticks=0;for(let i=3;i>=0;i--)ticks=ticks*256+bus.getByteDirect(0x46c+i);const timing={hostMonotonicMs:performance.now(),guestTicks:ticks,cpuCycles:cpu.getCycles(),running:cpu.isRunning()};fs.writeFileSync(prefix+'-'+tag+'.json',JSON.stringify({timing,videoMode:bus.getByteDirect(0x449),memory:v.adwMemory,atc:v.regATCData,crtc:v.regCRTData}));console.log('SNAP',tag,{f8,msw:cpu.regCR0,videoMode:bus.getByteDirect(0x449)});}
if(mode==='gameplay'||mode==='timing'){const mouse=Component.getComponentByType('Mouse');mouse.scale=1;
setTimeout(()=>{snap('initial');console.log('MOUSE',mouse.isActive(),mouse.scale);mouse.moveMouse(-1000,-1000);},12000);
setTimeout(()=>{mouse.moveMouse(50,72)},15000);
setTimeout(()=>{snap('position');mouse.clickMouse(0,true)},18000);
setTimeout(()=>mouse.clickMouse(0,false),18500);
if(mode==='timing'){
for(let i=20;i<=25;i++)setTimeout(()=>snap('second-'+i),i*1000);
setTimeout(()=>{snap('before-pause');cpu.stopCPU();},26000);
setTimeout(()=>{snap('paused');cpu.startCPU();},28000);
setTimeout(()=>{snap('resumed');mouse.moveMouse(56,0);},30000);
setTimeout(()=>mouse.clickMouse(2,true),31000);
setTimeout(()=>mouse.clickMouse(2,false),31500);
setTimeout(()=>snap('flag'),31800);
setTimeout(()=>mouse.clickMouse(2,true),32000);
setTimeout(()=>mouse.clickMouse(2,false),32500);
setTimeout(()=>snap('question'),32800);
setTimeout(()=>mouse.clickMouse(2,true),33000);
setTimeout(()=>mouse.clickMouse(2,false),33500);
setTimeout(()=>snap('blank'),33800);
setTimeout(()=>kbd.injectKeys('$f2',20),34000);
setTimeout(()=>snap('reset'),36000);
}else{
setTimeout(()=>snap('reveal'),22000);
setTimeout(()=>mouse.moveMouse(56,0),23000);
setTimeout(()=>mouse.clickMouse(2,true),25000);
setTimeout(()=>mouse.clickMouse(2,false),25500);
setTimeout(()=>snap('flag-timer'),29000);
setTimeout(()=>kbd.injectKeys('$f2',20),30000);
}
}
setTimeout(()=>{cpu.stopCPU();fs.writeFileSync(prefix+'-console.txt',output); let v=video.cardEGA;fs.writeFileSync(prefix+'-ega.json',JSON.stringify({videoMode:bus.getByteDirect(0x449),memory:v.adwMemory,atc:v.regATCData,crtc:v.regCRTData}));const report={sourceDiskSha256,sourceDiskUnchanged:sourceDiskSha256===createHash('sha256').update(fs.readFileSync(path.join(base,'disk.json'))).digest('hex'),diskSha256,cpu:80286,ramKiB:640,clockMultiplier:1,speedMultiplier:1,coreCommit:lock.commit,mode,interruptF8Count:f8,msw:cpu.regCR0,protectedMode:!!(cpu.regCR0&1),videoMode:bus.getByteDirect(0x449),qualification:'Headless PCjs source core; reconstructed EGA VRAM; not browser QA, not 8088 proof',consoleOutput:output};fs.writeFileSync(prefix+'-report.json',JSON.stringify(report,null,2));console.log('FINAL',report);process.exit(0)},mode==='timing'?38000:35000);
