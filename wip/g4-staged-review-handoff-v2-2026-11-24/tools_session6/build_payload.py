#!/usr/bin/env python3
# Build the session-6 payload for the push: per-stage zips (no .git dirs, no package copies, no key material)
# plus plain-text files; then scan everything for credential-like content. Never prints a secret value.
import os, re, sys, zipfile, hashlib, shutil
S='/tmp/claude-0/-home-claude/d441201d-0373-573d-8f64-186072f858d3/scratchpad'
A=S+'/a9'; OUT=S+'/push_stage/wip/g4-staged-review-handoff-v2-2026-11-24/session6_2026-11-22_to_24_second_run'
if os.path.exists(S+'/push_stage'): shutil.rmtree(S+'/push_stage')
os.makedirs(OUT+'/reports'); os.makedirs(OUT+'/prompts_used'); os.makedirs(OUT+'/package')
SKIP_DIRS={'.git','pkg','__pycache__'}
SKIP_FILES={'pkgcopy.zip','pkg.zip'}
SKIP_EXT=('.pem','.key')
def walk(root):
    for dp,dn,fn in os.walk(root):
        dn[:]=sorted(d for d in dn if d not in SKIP_DIRS)
        for f in sorted(fn):
            if f in SKIP_FILES or f.endswith(SKIP_EXT): continue
            p=os.path.join(dp,f)
            if os.path.islink(p): continue
            yield p
stats={}
for st,name in (('stage_S3','stage_S3_scripts_and_evidence.zip'),('stage_S6','stage_S6_scripts_and_evidence.zip'),('stage_S7','stage_S7_scripts_and_evidence.zip'),('stage_S8','stage_S8_PARTIAL_scripts_and_evidence.zip')):
    n=0
    with zipfile.ZipFile(OUT+'/'+name,'w',zipfile.ZIP_DEFLATED) as z:
        for p in walk(A+'/'+st):
            z.write(p, os.path.relpath(p, A)); n+=1
    stats[name]=n
# plain files
shutil.copy(A+'/COMMON_PREAMBLE.md', OUT+'/COMMON_PREAMBLE_second_run.md')
shutil.copy(A+'/package/g4_rev3_independent_review_package.zip', OUT+'/package/')
for f in os.listdir(A+'/prompts_used'): shutil.copy(A+'/prompts_used/'+f, OUT+'/prompts_used/')
for f in os.listdir(A+'/reports'): shutil.copy(A+'/reports/'+f, OUT+'/reports/')
shutil.copy(A+'/stage_S8/COMPARISON.tsv', OUT+'/reports/S8_PARTIAL_COMPARISON.tsv')
shutil.copy(A+'/stage_S8/comparison_rows.txt', OUT+'/reports/S8_PARTIAL_comparison_rows.txt')
shutil.copy(A+'/stage_S3/SUMMARY.tsv', OUT+'/reports/S3_SUMMARY.tsv')
shutil.copy(A+'/stage_S6/summary.tsv', OUT+'/reports/S6_summary.tsv')
shutil.copy(A+'/stage_S7/SUMMARY_TABLE.tsv', OUT+'/reports/S7_SUMMARY_TABLE.tsv')
print('zip entry counts',stats)
# ---- scan
vals=[]
BENIGN={"git@github.com:","ssh://git@github.com/"}
for k,v in os.environ.items():
    if re.search(r'TOKEN|SECRET|PASSWORD|KEY|AUTH|CRED|GIT_CONFIG_VALUE',k,re.I) and len(v)>=12 and not v.startswith("/") and v not in BENIGN:
        vals.append(v.encode())
pats=[re.compile(rb'ghp_[A-Za-z0-9]{20,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{20,}'),re.compile(rb'gh[osur]_[A-Za-z0-9]{20,}'),
      re.compile(rb'sk-ant-[A-Za-z0-9_-]{10,}'),re.compile(rb'AKIA[0-9A-Z]{16}'),re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
      re.compile(rb'(?i)authorization:\s*(basic|bearer)\s+[A-Za-z0-9+/=._-]{12,}')]
hits={}
def scan(name,data):
    for i,v in enumerate(vals):
        if v in data: hits.setdefault(name,[]).append('envvalue#%d'%i)
    for p in pats:
        m=p.search(data)
        if m: hits.setdefault(name,[]).append('pattern:'+p.pattern[:24].decode())
nfiles=0
for dp,dn,fn in os.walk(S+'/push_stage'):
    for f in fn:
        p=os.path.join(dp,f); nfiles+=1
        data=open(p,'rb').read()
        if f.endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for zi in z.infolist():
                    scan(f+'!'+zi.filename, z.read(zi)); nfiles+=1
        else: scan(os.path.relpath(p,S+'/push_stage'),data)
print('scanned entries',nfiles,'env credential-like values checked',len(vals))
print('HITS',len(hits))
for k,v in list(hits.items())[:40]: print('  ',k,v)
