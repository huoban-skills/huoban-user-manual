#!/usr/bin/env python3
"""hl.py <out.png> [--selector S] [--prep JS] [--prep-wait N] spec...
spec forms:
  'text|up'             exact visible leaf text, climb up N parents
  '~text|up'            leaf text contains
  'css:<sel>'           first visible match; 'css:<sel>@<text>' = first visible match containing text
  'cssunion:<sel>'      union box of all visible matches
  'union:tA;tB|up'      union box of ancestors of several leaf texts
"""
import sys, subprocess, json, os
from pathlib import Path
os.environ["PYTHONIOENCODING"]="utf-8"; os.environ["PYTHONUTF8"]="1"
B=str(Path(__file__).resolve().with_name("browser.py"))
args=sys.argv[1:]; out=args.pop(0); extra=[]
scope=None
while args and args[0].startswith("--"):
    k=args.pop(0)
    if k=="--scope": scope=args.pop(0)
    else: extra+=[k,args.pop(0)]
specs=args
J=json.dumps
LEAF="[...document.querySelectorAll('*')].filter(x=>{const r=x.getBoundingClientRect();return "+("x.closest("+json.dumps(scope)+")&&" if scope else "")+"x.children.length===0&&r.width>1&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth&&x.checkVisibility()})"
def climb(up): return f"for(let k=0;k<{int(up)};k++)e=e.parentElement;"
def union_js(i, els_expr, label_expr):
    return ("(()=>{const els=%s;if(!els.length)return false;let l=1e9,t=1e9,r=0,b=0;"
            "els.forEach(e=>{const q=e.getBoundingClientRect();l=Math.min(l,q.left);t=Math.min(t,q.top);r=Math.max(r,q.right);b=Math.max(b,q.bottom)});"
            "const d=document.createElement('div');d.className='__hbu';d.setAttribute('data-hb','%d');d.setAttribute('aria-label',%s);"
            "d.style.cssText='position:fixed;left:'+l+'px;top:'+t+'px;width:'+(r-l)+'px;height:'+(b-t)+'px;pointer-events:none;z-index:2147483646';"
            "document.body.appendChild(d);return els.length})()") % (els_expr, i, label_expr)
parts=[]
CLAMP="(()=>{const M=9;[...document.querySelectorAll('[data-hb]')].forEach(e=>{if(e.classList.contains('__hbu')){const r=e.getBoundingClientRect();const l=Math.max(M,r.left),t=Math.max(M,r.top),rr=Math.min(innerWidth-M,r.right),b=Math.min(innerHeight-M,r.bottom);e.style.left=l+'px';e.style.top=t+'px';e.style.width=(rr-l)+'px';e.style.height=(b-t)+'px';return}const r=e.getBoundingClientRect();const l=Math.max(M,r.left),t=Math.max(M,r.top),rr=Math.min(innerWidth-M,r.right),b=Math.min(innerHeight-M,r.bottom);if(l===r.left&&t===r.top&&rr===r.right&&b===r.bottom)return;const n=e.getAttribute('data-hb');e.removeAttribute('data-hb');const d=document.createElement('div');d.className='__hbu';d.setAttribute('data-hb',n);d.setAttribute('aria-label',(e.innerText||'').trim().slice(0,60));d.style.cssText='position:fixed;left:'+l+'px;top:'+t+'px;width:'+(rr-l)+'px;height:'+(b-t)+'px;pointer-events:none;z-index:2147483646';document.body.appendChild(d)});return 1})()"
for i,s in enumerate(specs,1):
    if s.startswith("union:"):
        body,up=s[6:].rsplit("|",1); texts=[t for t in body.split(";") if t]
        els=f"{J(texts)}.map(t=>{{let e={LEAF}.find(x=>x.textContent.trim()===t);if(!e)return null;{climb(up)}return e}}).filter(Boolean)"
        parts.append(union_js(i, els, J(" ".join(texts))))
    elif s.startswith("js:"):
        parts.append(f"(()=>{{const e=({s[3:]});if(!e)return false;e.setAttribute('data-hb','{i}');return true}})()")
    elif s.startswith("gridrow:"):
        # gridrow:<headerText>|<ncells>[|rowIndex]  -> union of first n cells of a row in the grid whose header contains text
        body=s[8:].split("|"); ht=body[0]; n=int(body[1]) if len(body)>1 else 6; ri=int(body[2]) if len(body)>2 else 0
        els=(f"(()=>{{const g=[...document.querySelectorAll('.ag-root')].find(r=>r.checkVisibility()&&r.querySelector('.ag-header')&&r.querySelector('.ag-header').innerText.includes({J(ht)}));"
             f"if(!g)return [];const row=g.querySelector(\".ag-center-cols-container .ag-row[row-index='{ri}']\");if(!row)return [];"
             f"return [...row.querySelectorAll('.ag-cell')].filter(c=>{{const q=c.getBoundingClientRect();return q.width>1&&q.right<innerWidth&&q.left>0}}).slice(0,{n})}})()")
        parts.append(union_js(i, els, "els.map(e=>e.innerText.trim().slice(0,20)).join(' ')"))
    elif s.startswith("cssunion:"):
        sc=("&&x.closest("+J(scope)+")") if scope else ""
        els=f"[...document.querySelectorAll({J(s[9:])})].filter(x=>{{const q=x.getBoundingClientRect();return q.width>1&&q.top>=0&&q.bottom<=innerHeight&&x.checkVisibility(){sc}}})"
        parts.append(union_js(i, els, "els.map(e=>(e.innerText||(e.querySelector('input')||{}).placeholder||'').trim().slice(0,30)).join(' ')"))
    elif s.startswith("css:"):
        sel=s[4:]; txt=None; up="0"
        if "|" in sel: sel,up=sel.rsplit("|",1)
        if "@" in sel: sel,txt=sel.rsplit("@",1)
        cond=f"&&x.textContent.includes({J(txt)})" if txt else ""
        parts.append(f"(()=>{{const a=(x)=>{{const r=x.getBoundingClientRect();return r.width*r.height}};let e=[...document.querySelectorAll({J(sel)})].filter(x=>x.getBoundingClientRect().width>1&&x.checkVisibility(){cond}).sort((p,q)=>a(p)-a(q))[0];if(!e)return false;{climb(up)}e.setAttribute('data-hb','{i}');return true}})()")
    else:
        contains=s.startswith("~")
        if contains: s=s[1:]
        text,up=s.rsplit("|",1) if "|" in s else (s,"0")
        m=".includes(t)" if contains else "===t"
        parts.append(f"(()=>{{const t={J(text)};let e={LEAF}.find(x=>x.textContent.trim(){m});if(!e)return false;{climb(up)}e.setAttribute('data-hb','{i}');return true}})()")
prep_after="["+",".join(parts)+","+json.dumps(clamp)[1:-1].replace("\\\"","\"")+"]" if False else "(()=>{const r=["+",".join(parts)+"];"+CLAMP+";return r})()"
hl=",,".join(f'[data-hb="{i}"]' for i in range(1,len(specs)+1))
cmd=[sys.executable,B,"shot","--path",out]+extra
if specs: cmd+=["--prep-after",prep_after,"--highlight",hl]
r=subprocess.run(cmd)
subprocess.run([sys.executable,B,"eval","--js","document.querySelectorAll('.__hbu').forEach(e=>e.remove());document.querySelectorAll('[data-hb]').forEach(e=>e.removeAttribute('data-hb'));1"],stdout=subprocess.DEVNULL)
sys.exit(r.returncode)
