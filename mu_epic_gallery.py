"""
Sinh epic_gallery.html - xem 91 map .att S21 (epicmu) da giai ma.
Chay: python mu_epic_gallery.py

Tinh nang:
  - Luoi thumbnail toan bo map (256x256 tile).
  - Click vao 1 map de PHONG TO toan man hinh (modal), xem ky tung tile.
  - Trong che do phong to: di chuot hien toa do tile (x,y) truc tiep; click de
    chon/danh dau 1 toa do, hien thanh toa do hien tai + toa do da chon de
    tinh toan (copy duoc). Nut dong / Esc de thoat.
"""
import os, glob, json, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "att_samples")

# Ten map pho bien (WorldN -> ten), cap nhat tu Test.htm (nguoi dung doi ten).
# Map khong co o day -> hien thi khong ten, nam cuoi cung sau khi sap xep.
NAMES = {
    1:"Lorencia",2:"Dungeon",3:"Devias",4:"Noria",5:"Lost Tower",7:"Arena",
    8:"Atlans",9:"Tarkan",10:"Devil Square",11:"Icarus",12:"Blood Castle",
    19:"Chaos Catsle",25:"Kalima2",31:"Valley of Loren 2",32:"Land of Trials",
    34:"Aida",35:"Crywolf 3",38:"Kanturu Ruins",39:"Kanturu 1 (Remain)",
    40:"Kanturu 2 (Refinery Tower)",42:"Barracks of Balgass",43:"Balgass Refuge",
    47:"Illusion Temple 1",52:"Elbeland",57:"Swamp of Calmness",58:"Raklion",
    59:"Hatchery (Raklion Boss)",64:"Vulcanus",65:"Duel Arena",69:"Double Goer",
    80:"Loren Market",81:"Karutan 1",82:"Karutan 2",92:"Acheron",94:"Null",
    95:"Debenter",96:"Debenter",99:"Illusion Temple League",101:"Urk Mountain",
    103:"Event",111:"Nars",113:"Ferea",114:"Nixie Lake",121:"Deep Dungeon 5",
    122:"Test Area",124:"Kubera Mine",129:"Atlans Abyss",134:"Arenil Temple",
    135:"Gray Aida",136:"Old Kethotum",137:"Old Kethotum",138:"Kanturu Underground",
    139:"Ignis Vulcanus",140:"Battle Boss",141:"Bloody Tarkan",142:"Tormenta Island",
    143:"Twisted Karutan",144:"Kardamahal Underground Temple",
    117:"Deep Dungeon 1",118:"Deep Dungeon 2",119:"Deep Dungeon 3",120:"Deep Dungeon 4",
    130:"Atlans Abyss 2",131:"Atlans Abyss 3",132:"Scotch Canyon",133:"Redsmoke Icarus",
    145:"Swamp of Despair",146:"Aquilas Santuary",147:"Forgotten Ralkion",
}

items = []
seen = {}   # md5 -> file da chon (de loai map trung nhau, giu map unique)
for png in sorted(glob.glob(os.path.join(SAMPLES, "World*", "EncTerrain*.att.png"))):
    base = os.path.basename(png)
    wd = os.path.basename(os.path.dirname(png))
    try:
        num = int(''.join(ch for ch in wd if ch.isdigit()))
    except ValueError:
        num = 0
    h = hashlib.md5(open(png, "rb").read()).hexdigest()
    if h in seen:
        # cung 1 anh voi map da co -> bo qua (tranh trung lap)
        print(f"  Bo qua map trung: {os.path.relpath(png, SAMPLES)} (trung {seen[h]})")
        continue
    seen[h] = os.path.relpath(png, SAMPLES).replace("\\", "/")
    label = NAMES.get(num, "")
    m = base.replace("EncTerrain","").replace(".att.png","")
    items.append({"file": seen[h], "wd": wd, "num": num, "label": label, "name": base})

# sap xep: map co ten ro rang len truoc (theo World tang dan),
# map khong ten / None nam cuoi cung (giu thu tu World).
items.sort(key=lambda x: (0, x["num"]) if NAMES.get(x["num"]) else (1, x["num"]))

html = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MU S21 (epicmu) — Bản đồ đi được (có phóng to)</title>
<style>
 body{background:#0f1115;color:#e6e6e6;font:14px/1.5 system-ui,sans-serif;margin:0;padding:20px}
 h1{font-size:20px;margin:0 0 4px}
 p.sub{color:#9aa;margin:0 0 16px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 18px;font-size:12px}
 .legend span{display:flex;align-items:center;gap:6px}
 .sw{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid #333}
 .row{display:flex;gap:12px;flex-wrap:wrap}
 .card{background:#171a21;border:1px solid #262b36;border-radius:8px;padding:8px;width:140px;cursor:pointer;transition:.15s}
 .card:hover{border-color:#4af;transform:translateY(-2px)}
 .card h3{margin:0 0 4px;font-size:13px}
 .card .lbl{color:#9aa;font-size:11px;margin-bottom:4px;min-height:14px}
 canvas{image-rendering:pixelated;width:124px;height:124px;border:1px solid #333;display:block}
 #tip{position:fixed;background:#000c;padding:4px 8px;border-radius:4px;font-size:12px;pointer-events:none;display:none;z-index:9}
 /* Modal phong to */
 #ov{position:fixed;inset:0;background:#000d;display:none;z-index:50;flex-direction:column;align-items:center;justify-content:center;padding:16px}
 #ov.on{display:flex}
 #ov{overflow:hidden}
 #ov header{width:90%;display:flex;align-items:center;gap:12px;margin-bottom:8px}
 #ov header h2{margin:0;font-size:16px}
 #ov header .x{margin-left:auto;cursor:pointer;background:#222;border:1px solid #444;border-radius:6px;padding:4px 10px}
 #ov header .x:hover{background:#333}
 #big{image-rendering:pixelated;background:#000;border:1px solid #555;width:90vw;height:90vh;max-width:90%;max-height:90%;cursor:crosshair}
 #ov .bar{width:90%;display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:8px;font-size:13px}
 #ov .bar .k{color:#9aa}
 #ov .bar code{background:#1b1f29;padding:2px 6px;border-radius:4px;border:1px solid #2a2f3a;user-select:all}
 #ov .bar button{background:#1f6feb;border:0;border-radius:6px;color:#fff;padding:5px 10px;cursor:pointer}
 #ov .bar button:hover{background:#388bfd}
</style></head><body>
<h1>MU S21 (epicmu) — Bản đồ đi được</h1>
<p class="sub">Nguồn: client epicmu <code>EncTerrain*.att</code> giải mã. Đen=đi được, trắng=tường, xanh=safe, xanh dương=nước/vực. <b>Click vào 1 map để phóng to</b> và xem/tính toạ độ.</p>
<div class="legend">
 <span><i class="sw" style="background:#000"></i>Đi được</span>
 <span><i class="sw" style="background:#fff"></i>Tường</span>
 <span><i class="sw" style="background:#00b400"></i>Safe</span>
 <span><i class="sw" style="background:#0078ff"></i>Nước/Vực</span>
</div>
<div id="tip"></div>
<div class="row" id="row"></div>

<div id="ov">
  <header>
    <h2 id="ovTitle"></h2>
    <div class="x" id="ovClose">Đóng (Esc)</div>
  </header>
  <canvas id="big" width="256" height="256"></canvas>
  <div class="bar">
    <span class="k">Toạ độ chuột:</span> <code id="curPos">—</code>
    <span class="k">Đã chọn:</span> <code id="selPos">—</code>
    <button id="copyCur">Copy chuột</button>
    <button id="copySel">Copy đã chọn</button>
    <span class="k" id="hint">Click trên ảnh để chọn toạ độ.</span>
  </div>
</div>

<script>
const ITEMS = __ITEMS__;
const N = 256;
const row=document.getElementById('row');
const tip=document.getElementById('tip');

// Ten map tu chinh sua (luu localStorage). Key = so World (hoac ten thu muc neu khong co so).
const LS_KEY='mu_map_names';
let NAMES=JSON.parse(localStorage.getItem(LS_KEY)||'{}');
function nameKey(it){return it.num?(''+it.num):it.wd;}
function mapName(it){const k=nameKey(it);return NAMES[k]!==undefined?NAMES[k]:it.label;}
function saveName(it,nv){const k=nameKey(it);if(nv===''||nv===null)delete NAMES[k];else NAMES[k]=nv;localStorage.setItem(LS_KEY,JSON.stringify(NAMES));}

for(const it of ITEMS){
  const c=document.createElement('div');c.className='card';
  const h=document.createElement('h3');h.textContent=it.num?('World'+it.num):it.wd;
  const l=document.createElement('div');l.className='lbl';l.textContent=mapName(it);
  l.style.cursor='pointer';l.title='Click để đổi tên map';
  l.addEventListener('click',e=>{e.stopPropagation();
    const nv=prompt('Tên map mới:',mapName(it));
    if(nv===null)return;
    saveName(it,nv.trim());
    l.textContent=mapName(it);
    if(curImgIt&&nameKey(curImgIt)===nameKey(it))ovTitle.textContent=titleFor(curImgIt);
  });
  const cv=document.createElement('canvas');cv.width=N;cv.height=N;
  c.appendChild(h);c.appendChild(l);c.appendChild(cv);row.appendChild(c);
  const ctx=cv.getContext('2d');const img=new Image();
  img.onload=()=>ctx.drawImage(img,0,0);img.src=it.file;
  cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect();
    const x=Math.floor((e.clientX-r.left)/r.width*N),y=Math.floor((e.clientY-r.top)/r.height*N);
    tip.style.display='block';tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';
    tip.textContent=it.file.replace('.att.png','')+' ('+x+', '+y+')';});
  cv.addEventListener('mouseleave',()=>tip.style.display='none');
  c.addEventListener('click',()=>openZoom(it));
}

// ===== Phong to =====
const ov=document.getElementById('ov');
const big=document.getElementById('big');
const bctx=big.getContext('2d');
const ovTitle=document.getElementById('ovTitle');
const curPos=document.getElementById('curPos');
const selPos=document.getElementById('selPos');
let curImg=null, sel=null;

function titleFor(it){return (it.num?('World'+it.num):it.wd)+(mapName(it)?' — '+mapName(it):'');}
let curImgIt=null;
function openZoom(it){
  curImgIt=it;
  curImg=it.file;
  ovTitle.textContent=titleFor(it);
  const img=new Image();
  img.onload=()=>bctx.drawImage(img,0,0);
  img.src=it.file;
  sel=null; selPos.textContent='—';
  ov.classList.add('on');
}
function closeZoom(){ov.classList.remove('on');}
document.getElementById('ovClose').addEventListener('click',closeZoom);
ov.addEventListener('click',e=>{if(e.target===ov)closeZoom();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeZoom();});

function tileOf(e){
  const r=big.getBoundingClientRect();
  let x=Math.floor((e.clientX-r.left)/r.width*N);
  let y=Math.floor((e.clientY-r.top)/r.height*N);
  x=Math.max(0,Math.min(N-1,x)); y=Math.max(0,Math.min(N-1,y));
  return {x,y};
}
big.addEventListener('mousemove',e=>{const p=tileOf(e);curPos.textContent='('+p.x+', '+p.y+')';});
big.addEventListener('click',e=>{const p=tileOf(e);sel={x:p.x,y:p.y};selPos.textContent='('+p.x+', '+p.y+')';});
document.getElementById('copyCur').addEventListener('click',()=>navigator.clipboard.writeText(curPos.textContent));
document.getElementById('copySel').addEventListener('click',()=>navigator.clipboard.writeText(selPos.textContent));
</script>
</body></html>"""
html = html.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
out = os.path.join(SAMPLES, "epic_gallery.html")
open(out, "w", encoding="utf-8").write(html)
print(f"Da sinh {out} voi {len(items)} map S21 (co phong to).")
