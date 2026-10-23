"""Non-rendering DOM behavior seam; no browser, network or screenshot tooling."""
import pathlib
import subprocess
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]


class TerminalLogsTests(unittest.TestCase):
    def test_selection_enrichment_filter_pause_clear_and_text_safety(self):
        harness=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element {
 constructor(){this.children=[];this.events={};this.attributes={};this.style={};this.value='';this.hidden=false;this.textContent='';this.classes=new Set();this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),toggle:(x,on)=>on?this.classes.add(x):this.classes.delete(x)};}
 appendChild(child){this.children.push(child);return child;}
 replaceChildren(...children){this.children=children;this.textContent='';}
 addEventListener(event,handler){this.events[event]=handler;}
 setAttribute(key,value){this.attributes[key]=String(value);}
 focus(){}
}
const elements=new Map();
const document={getElementById:id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)},createElement:()=>new Element(),querySelectorAll:()=>[],addEventListener:()=>{},body:new Element()};
let clears=0;const window={addEventListener:()=>{},pywebview:{api:{clear_connections:async()=>{clears++}}}};
const context=vm.createContext({document,window,console,Date,setInterval:()=>{},clearInterval:()=>{},setTimeout:()=>{},clearTimeout:()=>{}});
const html=fs.readFileSync(process.argv[1],'utf8');
vm.runInContext([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n'),context);
const run=source=>vm.runInContext(source,context);
(async()=>{
 run(`upsertConnections([{kind:'connection',connection_key:'one',timestamp:1,process:'C:\\\\Apps\\\\chrome.exe',destination:'<img onerror=alert(1)>',address:'203.0.113.1',protocol:'tls',route:'proxy-out'}]);renderConnections();selectConnection('one');`);
 assert.equal(document.getElementById('connectionInspectorHost').textContent,'<img onerror=alert(1)>');
 assert.equal(document.getElementById('connectionInspectorHost').children.length,0);
 assert.equal(run("connectionRoute({proxy_id:'missing',route:'proxy-out'})"),'Прокси');
 run("proxyList=[{id:'known',country_code:'US'}]");
 assert.equal(run("connectionRoute({proxy_id:'known',route:'proxy-out'})"),'US');
 run(`upsertConnections([{kind:'connection',connection_key:'one',timestamp:1,destination:'example.com',protocol:'tls',route:'proxy-out'}]);renderConnections();`);
 assert.equal(run('selectedConnectionKey'),'one');
 assert.equal(document.getElementById('connectionInspectorHost').textContent,'example.com');
 run(`upsertConnections([{kind:'connection',connection_key:'two',timestamp:2,destination:'example.net'}]);renderConnections();`);
 document.getElementById('connectionRows').children[1].events.keydown({key:'Enter',preventDefault:()=>{}});
 assert.equal(run('selectedConnectionKey'),'two');
 run('toggleConnectionPause()');assert.equal(run('connectionPaused'),true);
 run('toggleConnectionPause()');assert.equal(run('connectionPaused'),false);
 document.getElementById('connectionFilter').value='example.com';run('renderConnections()');
 assert.equal(document.getElementById('connectionRows').children.length,1);
 assert.equal(run('selectedConnectionKey'),null);
 assert.equal(document.getElementById('connectionCount').textContent,'1 / 2');
 run("selectConnection('one');upsertConnections([]);connectionRows=connectionRows.filter(row=>row.connection_key!=='one');renderConnections()");
 assert.equal(run('selectedConnectionKey'),null);
 await run('clearConnections()');assert.equal(clears,1);assert.equal(run('connectionRows.length'),0);
 assert.equal(document.getElementById('connectionInspectorHost').textContent,'Выберите строку');
 run("switchTab('connections')");assert(document.body.classes.has('terminal-logs'));
 run("switchTab('home')");assert(!document.body.classes.has('terminal-logs'));
 console.log('terminal behavior passed');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result=subprocess.run(['node','-e',harness,str(ROOT/'gui/web/index.html')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)

