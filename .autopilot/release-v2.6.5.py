"""Publish only KROTTUN v2.6.5 using pu-pu-puu from GCM; never prints secrets."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import requests

ROOT=Path(__file__).resolve().parents[1]
REPO='pu-pu-puu/KROTTUN'
TAG='v2.6.5'
LOGIN='pu-pu-puu'
API='https://api.github.com'


def client():
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never')
    result=subprocess.run(['git','-c','credential.username='+LOGIN,'credential','fill'],
        input='protocol=https\nhost=github.com\nusername='+LOGIN+'\n\n',text=True,
        capture_output=True,env=env,cwd=ROOT,timeout=30)
    if result.returncode: raise RuntimeError('Git Credential Manager did not supply the requested account')
    data=dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if data.get('username')!=LOGIN or not data.get('password'):
        raise RuntimeError('Git credential account mismatch')
    session=requests.Session();session.trust_env=False
    session.headers.update({'Authorization':'Bearer '+data['password'],'Accept':'application/vnd.github+json',
        'X-GitHub-Api-Version':'2022-11-28','User-Agent':'KROTTUN-release'})
    profile=session.get(API+'/user',timeout=20)
    if profile.status_code!=200 or profile.json().get('login')!=LOGIN:
        raise RuntimeError('Authenticated GitHub user is not pu-pu-puu')
    return session


def request(session,method,path,expected=(200,),**kwargs):
    url=path if path.startswith('https://') else API+path
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in ('api.github.com','uploads.github.com'):
        raise RuntimeError('Unapproved API host')
    response=session.request(method,url,timeout=kwargs.pop('timeout',30),allow_redirects=False,**kwargs)
    if response.status_code not in expected:
        raise RuntimeError('GitHub API '+method+' failed with status '+str(response.status_code))
    return response


def main():
    action=sys.argv[1] if len(sys.argv)>1 else 'inspect'
    if action not in ('inspect','publish','verify'): raise RuntimeError('Unknown action')
    session=client()
    print('Authenticated account:',LOGIN)
    path='/repos/'+REPO
    if action=='inspect':
        repo=request(session,'GET',path).json()
        print('Repository:',repo['full_name'],'push permission:',repo.get('permissions',{}).get('push'))
        releases=request(session,'GET',path+'/releases?per_page=5').json()
        print(json.dumps([{'tag':r['tag_name'],'draft':r['draft'],'author':r['author']['login'],
            'assets':[{'name':a['name'],'uploader':a['uploader']['login']} for a in r['assets']]} for r in releases],ensure_ascii=False))
        return
    expected_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    ref=request(session,'GET',path+'/git/ref/tags/'+TAG).json()
    obj=ref['object']
    if obj['type']=='tag': obj=request(session,'GET',path+'/git/tags/'+obj['sha']).json()['object']
    if obj['type']!='commit' or obj['sha']!=expected_sha: raise RuntimeError('Remote tag differs from local HEAD')
    head=request(session,'GET',path+'/git/ref/heads/main').json()['object']['sha']
    if head!=expected_sha: raise RuntimeError('Remote main differs from release HEAD')
    executable=ROOT/'dist/v2.6.5/KROTTUN.exe'
    checksum=ROOT/'dist/v2.6.5/KROTTUN.exe.sha256'
    expected_hash=hashlib.sha256(executable.read_bytes()).hexdigest()
    if checksum.read_text().strip()!=expected_hash+'  KROTTUN.exe': raise RuntimeError('Checksum file mismatch')
    existing=request(session,'GET',path+'/releases/tags/'+TAG,expected=(200,404))
    if action=='publish':
        if existing.status_code!=404: raise RuntimeError('Release already exists; refusing overwrite')
        release=request(session,'POST',path+'/releases',expected=(201,),json={
            'tag_name':TAG,'target_commitish':expected_sha,'name':'KROTTUN 2.6.5 — надёжность и понятные состояния защиты',
            'body':(ROOT/'.autopilot/release-v2.6.5.md').read_text(encoding='utf-8-sig'),
            'draft':True,'prerelease':False}).json()
        if release['author']['login']!=LOGIN: raise RuntimeError('Release author mismatch')
        upload=release['upload_url'].split('{',1)[0]
        for file,mime in ((executable,'application/vnd.microsoft.portable-executable'),(checksum,'text/plain')):
            with file.open('rb') as stream:
                asset=request(session,'POST',upload,expected=(201,),params={'name':file.name},
                    headers={'Content-Type':mime},data=stream,timeout=180).json()
            if asset['uploader']['login']!=LOGIN or asset['size']!=file.stat().st_size:
                raise RuntimeError('Uploaded asset identity or size mismatch')
            digest=asset.get('digest')
            if not digest or digest!='sha256:'+hashlib.sha256(file.read_bytes()).hexdigest():
                raise RuntimeError('Uploaded asset SHA256 unavailable or mismatched; draft retained')
            print('Verified uploaded asset:',file.name,'SHA256:',digest)
        release=request(session,'PATCH',path+'/releases/'+str(release['id']),json={'draft':False,'make_latest':'true'}).json()
    else:
        if existing.status_code!=200: raise RuntimeError('Published release missing')
        release=existing.json()
    if release['draft'] or release['prerelease'] or release['author']['login']!=LOGIN:
        raise RuntimeError('Published release state or author mismatch')
    assets={a['name']:a for a in release['assets']}
    for file in (executable,checksum):
        asset=assets.get(file.name,{})
        if asset.get('uploader',{}).get('login')!=LOGIN or asset.get('digest')!='sha256:'+hashlib.sha256(file.read_bytes()).hexdigest():
            raise RuntimeError('Published asset mismatch')
    latest=request(session,'GET',path+'/releases/latest').json()
    if latest['tag_name']!=TAG: raise RuntimeError('Latest release is not v2.6.5')
    print(json.dumps({'release':release['html_url'],'author':release['author']['login'],'commit':expected_sha,
        'assets':[{'name':a['name'],'url':a['browser_download_url'],'sha256':a.get('digest')} for a in release['assets']]},ensure_ascii=False))

if __name__=='__main__':
    try: main()
    except Exception as error:
        # Never serialize HTTP exceptions/headers/credential helper output.
        print('Release operation failed:',str(error) if type(error) is RuntimeError else type(error).__name__,file=sys.stderr)
        raise SystemExit(1)
