import pathlib
import subprocess
import unittest


class ProtectionStripTests(unittest.TestCase):
    def test_truthful_states_recovery_busy_and_failure(self):
        script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();const element=()=>({textContent:'',hidden:false,disabled:false,attributes:{},setAttribute(k,v){this.attributes[k]=v},classList:{add(){},remove(){}}});
const document={getElementById:id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)},addEventListener(){}};
let calls=0,resolveRelease;const alerts=[];const intervals=[];const timers=[],cleared=new Set();
const window={addEventListener(){},pywebview:{api:{release_protection:()=>{calls++;return new Promise(resolve=>resolveRelease=resolve)},get_state:async()=>{throw new Error('disconnected')}}}};
const context=vm.createContext({document,window,console,Date,setInterval:fn=>intervals.push(fn),setTimeout(fn){const timer={fn};timers.push(timer);return timer},clearTimeout:timer=>cleared.add(timer),clearInterval(){},alert:message=>alerts.push(message)});
const html=fs.readFileSync(process.argv[1],'utf8');vm.runInContext([...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).join('\n'),context);
const run=s=>vm.runInContext(s,context);const get=id=>document.getElementById(id);
(async()=>{
 for(const [state,hidden,label] of [['unarmed',true,'Снята'],['protected',false,'Включена'],['blocked',false,'Интернет заблокирован'],['unknown',false,'Статус неизвестен'],['connecting',false,'Подключение'],['switching',false,'Переключение']]){
  run(`updateProtectionStrip('${state}')`);assert.equal(get('protectionRelease').hidden,hidden);assert.equal(get('protectionStatus').textContent,label);
 }
 run(`updateProtectionStrip('<img onerror=evil()>')`);assert.equal(get('protectionStrip').attributes['data-state'],'unknown');
 for(const invalid of ['null','undefined',"['protected']",'{}','true']) {run('updateProtectionStrip('+invalid+')');assert.equal(get('protectionStrip').attributes['data-state'],'unknown');}
 assert(!get('protectionStatus').textContent.includes('<img'));
 const first=run('releaseProtection()');run('releaseProtection()');assert.equal(calls,1);assert.equal(get('protectionRelease').disabled,true);
 resolveRelease({success:false,error:'Ошибка снятия'});await first;assert.equal(get('protectionRelease').disabled,false);assert.equal(get('protectionRelease').hidden,false);assert.equal(alerts.length,1);
 run('refreshState=async()=>{}');
 const second=run('releaseProtection()');resolveRelease({success:true});await second;
 assert.equal(get('protectionRelease').disabled,false);assert.equal(get('protectionRelease').hidden,true);
 run(`updateProtectionStrip('protected')`);await intervals[0]();assert.equal(get('protectionStrip').attributes['data-state'],'unknown');
 window.pywebview.api.get_state=async()=>({protection:'protected'});window.pywebview.api.get_connections=async()=>{throw new Error('source unavailable')};
 await intervals[0]();await intervals[1]();assert.equal(get('protectionStrip').attributes['data-state'],'protected');
 for(const state of ['unarmed','protected']) {
  window.pywebview.api.get_state=async()=>({protection:state});
  window.pywebview.api.get_connections=async()=>{assert(cleared.has(timers.at(-1)));return {source:'unavailable',rows:[],cursor:0}};
  await intervals[0]();await intervals[1]();assert.equal(get('protectionStrip').attributes['data-state'],state);assert.equal(get('protectionRelease').hidden,state==='unarmed');
 }
 let resolveState;window.pywebview.api.get_state=()=>new Promise(resolve=>resolveState=resolve);
 const expired=intervals[0]();timers.at(-1).fn();resolveState({protection:'protected'});await expired;
 assert.equal(get('protectionStrip').attributes['data-state'],'unknown');
 let journalCalls=0;window.pywebview.api.get_connections=()=>{journalCalls++;return new Promise(()=>{})};
 intervals[1]();
 window.pywebview.api.get_state=async()=>({protection:'unarmed'});
 await intervals[0]();await intervals[1]();
 assert.equal(journalCalls,1);assert.equal(get('protectionStrip').attributes['data-state'],'unarmed');assert.equal(get('protectionRelease').hidden,true);
 let stateCalls=0;window.pywebview.api.get_state=()=>{stateCalls++;return new Promise(()=>{})};
 run("updateProtectionStrip('protected')");intervals[0]();timers.at(-1).fn();await intervals[0]();
 assert.equal(stateCalls,1);assert.equal(get('protectionStrip').attributes['data-state'],'unknown');assert.equal(get('protectionRelease').hidden,false);
 console.log('protection behavior passed');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
        result=subprocess.run(['node','-e',script,str(pathlib.Path(__file__).resolve().parents[1]/'gui/web/index.html')],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
