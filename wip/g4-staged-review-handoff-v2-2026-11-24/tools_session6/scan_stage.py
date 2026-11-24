#!/usr/bin/env python3
import os, re, sys, zipfile
root=sys.argv[1]
vals=[v.encode() for k,v in os.environ.items() if re.search(r'TOKEN|SECRET|PASSWORD|KEY|AUTH|CRED|GIT_CONFIG_VALUE',k,re.I) and len(v)>=12 and not v.startswith('/') and v not in ('git@github.com:','ssh://git@github.com/')]
pats=[rb'ghp_[A-Za-z0-9]{20,}',rb'github_pat_[A-Za-z0-9_]{20,}',rb'gh[osur]_[A-Za-z0-9]{20,}',rb'sk-ant-[A-Za-z0-9_-]{10,}',rb'AKIA[0-9A-Z]{16}',rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',rb'(?i)authorization:\s*(basic|bearer)\s+[A-Za-z0-9+/=._-]{12,}']
pats=[re.compile(p) for p in pats]; hits=[]; n=0
def scan(name,d):
    global n; n+=1
    if any(v in d for v in vals) or any(p.search(d) for p in pats): hits.append(name)
for dp,dn,fn in os.walk(root):
    if '.git' in dn: dn.remove('.git')
    for f in fn:
        p=os.path.join(dp,f); d=open(p,'rb').read(); scan(p,d)
        if f.endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for zi in z.infolist(): scan(p+'!'+zi.filename,z.read(zi))
print('entries scanned',n,'values checked',len(vals),'HITS',len(hits)); [print(' ',h) for h in hits[:20]]
sys.exit(1 if hits else 0)
