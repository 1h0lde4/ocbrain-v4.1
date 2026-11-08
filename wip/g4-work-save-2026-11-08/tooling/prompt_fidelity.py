import sys
U,old,new=sys.argv[1:4]
orig=open(U,"rb").read()
def sec2(path):
    t=open(path,"rb").read().decode("utf-8")
    a=t.index("## 2. Original Starting Prompt"); b=t.index("## 3. Subsequent User Instructions")
    return t[a:b].encode("utf-8")
for name,p in (("older handoff da162e71",old),("repo handoff a41ca610",new)):
    s=sec2(p)
    print(f"{name}: section 2 = {len(s)} bytes; original prompt ({len(orig)} bytes) occurs verbatim inside it: {orig in s}; after stripping the prompt's own trailing newlines: {orig.strip() in s}")
