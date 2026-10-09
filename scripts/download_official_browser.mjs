// Public-file acquisition in a fresh browser profile; no user login or saved state.
import {spawn} from 'node:child_process';
import {mkdir, rename, writeFile} from 'node:fs/promises';
const port=29333;
await mkdir('/sources/browser', {recursive:true});
const chrome=spawn('/usr/bin/chromium', ['--headless=new','--no-sandbox','--disable-dev-shm-usage',
  '--user-data-dir=/tmp/office-source-browser','--remote-debugging-port='+port,
  '--proxy-server=http://127.0.0.1:22111','about:blank'], {stdio:'ignore'});
let ws;
const attempts=[];
try {
  let version;
  for(let i=0;i<80;i++) {
    try {version=await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();break;}catch{}
    await new Promise(r=>setTimeout(r,250));
  }
  if(!version)throw Error('browser did not start');
  ws=new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  let sequence=0;
  const pending=new Map(), downloads=new Map();
  ws.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.id && pending.has(m.id)){const {resolve,reject}=pending.get(m.id);pending.delete(m.id);m.error?reject(Error(m.error.message)):resolve(m.result);}
    if(m.method==='Browser.downloadWillBegin')downloads.set(m.params.guid,{...m.params,state:'inProgress'});
    if(m.method==='Browser.downloadProgress' && downloads.has(m.params.guid))Object.assign(downloads.get(m.params.guid),m.params);
  };
  const send=(method,params={},sessionId)=>new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
  });
  await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:'/sources/browser',eventsEnabled:true});
  const files=[
    {name:'oews_may2025_national.zip',page:'https://www.bls.gov/oes/tables.htm',url:'https://www.bls.gov/oes/special-requests/oesm25nat.zip'},
    {name:'retail_benchsales26.xlsx',page:'https://www.census.gov/retail/mrts/historic_releases.html',url:'https://www.census.gov/retail/mrts/www/benchmark/2026/excel/benchsales26.xlsx'},
    {name:'sba1919_2025.pdf',page:'https://legacy.sba.gov/document/sba-form-1919-borrower-information-form',url:'https://legacy.sba.gov/sites/default/files/2025-03/2025.02.27%20Form%201919%20-%20Updates%20(FINAL)_03-12-2025%20(1).pdf'}
  ];
  for(const file of files) {
    const {targetId}=await send('Target.createTarget',{url:'about:blank'});
    const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
    await send('Page.enable',{},sessionId);
    await send('Runtime.enable',{},sessionId);
    const before=new Set(downloads.keys());
    const row={...file,status:'failed'};
    try {
      await send('Page.navigate',{url:file.page},sessionId);
      await new Promise(r=>setTimeout(r,1500));
      const nav=await send('Page.navigate',{url:file.url},sessionId);
      row.navigation=nav;
      for(let i=0;i<120;i++){
        const download=[...downloads.values()].find(x=>!before.has(x.guid));
        if(download?.state==='completed'){
          await rename('/sources/browser/'+download.suggestedFilename,'/sources/browser/'+file.name);
          row.status='success';row.download=download;break;
        }
        if(download?.state==='canceled'){row.error='browser download canceled';break;}
        if(i===20){const text=await send('Runtime.evaluate',{expression:'document.body?.innerText',returnByValue:true},sessionId);row.page_text=text.result?.value?.slice(0,800);}
        await new Promise(r=>setTimeout(r,250));
      }
    }catch(e){row.error=String(e);}
    attempts.push(row);console.log(JSON.stringify(row));
    await send('Target.closeTarget',{targetId});
  }
}finally {
  await writeFile('/sources/browser/download_report.json',JSON.stringify(attempts,null,2)+'\n');
  ws?.close();chrome.kill('SIGTERM');
}
