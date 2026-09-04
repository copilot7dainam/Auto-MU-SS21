"""
Sinh epic_gallery.html - xem 91 map .att S21 (epicmu) da giai ma.
Chay: python mu_epic_gallery.py
"""
import os, glob, json

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "att_samples")

# Ten map pho bien (WorldN -> ten)
NAMES = {
    1:"Lorencia",2:"Dungeon",3:"Devias",4:"Lost Tower",5:"Exile",6:"Arena",
    7:"Atlans",8:"Tarkan",9:"Devil Square",10:"Icarus",11:"Blood Castle",
    12:"Chaos Castle",19:"Kalima1",25:"Kalima2",31:"Kalima3",32:"Kalima4",
    33:"Kalima5",34:"Kalima6",35:"Valley of Loren",36:"Land of Trial",37:"Aida",
    38:"Crywolf",39:"Kanturu",40:"Lorencia Castle",41:"Duel Arena",42:"Doppel",
    43:"Imperial",44:"Illusion Temple",46:"Raklion",47:"Santa",51:"Swamp",
    52:"Forgotten1",53:"Forgotten2",54:"Forgotten3",55:"Forgotten4",56:"Forgotten5",
    57:"Forgotten6",58:"Forgotten7",59:"Forgotten8",60:"Doppel2",62:"Nars",
    63:"Archangel",64:"Dungeon2",65:"Acheron",66:"Chaos",67:"Karutan",68:"Deep",
    69:"Karutan2",70:"Dino",71:"Hell",72:"Vulcan",73:"Torment",74:"Ferea",
    75:"Nixie",80:"Loren Market",81:"Hollow",82:"Zero",83:"MU2",92:"",94:"",95:"",96:"",99:"",
}

items = []
for png in sorted(glob.glob(os.path.join(SAMPLES, "World*", "EncTerrain*.att.png"))):
    base = os.path.basename(png)
    # WorldN folder
    wd = os.path.basename(os.path.dirname(png))
    try:
        num = int(''.join(ch for ch in wd if ch.isdigit()))
    except ValueError:
        num = 0
    label = NAMES.get(num, "")
    # index tu ten file EncTerrainN.att.png
    m = base.replace("EncTerrain","").replace(".att.png","")
    items.append({"file": os.path.relpath(png, SAMPLES).replace("\\","/"),
                  "wd": wd, "num": num, "label": label, "name": base})

# sap xep theo so
items.sort(key=lambda x: x["num"])

html = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MU S21 (epicmu) — 91 bản đồ đi được</title>
<style>
 body{background:#0f1115;color:#e6e6e6;font:14px/1.5 system-ui,sans-serif;margin:0;padding:20px}
 h1{font-size:20px;margin:0 0 4px}
 p.sub{color:#9aa;margin:0 0 16px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 18px;font-size:12px}
 .legend span{display:flex;align-items:center;gap:6px}
 .sw{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid #333}
 .row{display:flex;gap:12px;flex-wrap:wrap}
 .card{background:#171a21;border:1px solid #262b36;border-radius:8px;padding:8px;width:140px}
 .card h3{margin:0 0 4px;font-size:13px}
 .card .lbl{color:#9aa;font-size:11px;margin-bottom:4px;min-height:14px}
 canvas{image-rendering:pixelated;width:124px;height:124px;border:1px solid #333;display:block;cursor:crosshair}
 #tip{position:fixed;background:#000c;padding:4px 8px;border-radius:4px;font-size:12px;pointer-events:none;display:none;z-index:9}
</style></head><body>
<h1>MU S21 (epicmu) — 91 bản đồ đi được</h1>
<p class="sub">Nguồn: client epicmu <code>EncTerrain*.att</code> giải mã bằng pipeline xulek (FileCryptor/ModulusCryptor + BUX mask). Đen=đi được, trắng=tường, xanh=safe, xanh dương=nước/vực.</p>
<div class="legend">
 <span><i class="sw" style="background:#000"></i>Đi được</span>
 <span><i class="sw" style="background:#fff"></i>Tường</span>
 <span><i class="sw" style="background:#00b400"></i>Safe</span>
 <span><i class="sw" style="background:#0078ff"></i>Nước/Vực</span>
</div>
<div id="tip"></div>
<div class="row" id="row"></div>
<script>
const ITEMS = __ITEMS__;
const row=document.getElementById('row');
const tip=document.getElementById('tip');
for(const it of ITEMS){
  const c=document.createElement('div');c.className='card';
  const h=document.createElement('h3');h.textContent=it.num?('World'+it.num):it.wd;
  const l=document.createElement('div');l.className='lbl';l.textContent=it.label;
  const cv=document.createElement('canvas');cv.width=256;cv.height=256;cv.dataset.img=it.file;
  c.appendChild(h);c.appendChild(l);c.appendChild(cv);row.appendChild(c);
  const ctx=cv.getContext('2d');const img=new Image();
  img.onload=()=>ctx.drawImage(img,0,0);img.src=it.file;
  cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect();
    const x=Math.floor((e.clientX-r.left)/r.width*256),y=Math.floor((e.clientY-r.top)/r.height*256);
    tip.style.display='block';tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px';
    tip.textContent=it.file.replace('.att.png','')+' ('+x+', '+y+')';});
  cv.addEventListener('mouseleave',()=>tip.style.display='none');
}
</script>
</body></html>"""
html = html.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
out = os.path.join(SAMPLES, "epic_gallery.html")
open(out, "w", encoding="utf-8").write(html)
print(f"Da sinh {out} voi {len(items)} map S21.")
