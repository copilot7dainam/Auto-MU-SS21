"""
Sinh att_gallery.html - trang duyet 76 map .att (PNG walkable).
Chay: python mu_att_html.py   (can cac file att_samples/*.att.png da sinh)
"""
import os, glob, json
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, "att_samples")

# import ham stats cua viewer
spec = importlib.util.spec_from_file_location("v", os.path.join(HERE, "mu_att_view.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

# Ten map pho bien (OpenMU TerrainN)
MAP_NAMES = {
    "Terrain1": "Dungeon", "Terrain2": "Devias", "Terrain3": "Noria",
    "Terrain4": "Lost Tower", "Terrain5": "Exile", "Terrain6": "Arena",
    "Terrain7": "Atlans", "Terrain8": "Tarkan", "Terrain9": "Devil Square",
    "Terrain10": "Icarus", "Terrain11": "Blood Castle", "Terrain12": "Chaos Castle",
    "Terrain19": "Kalima1", "Terrain25": "Kalima2", "Terrain31": "Kalima3",
    "Terrain32": "Kalima4", "Terrain33": "Kalima5", "Terrain34": "Kalima6",
    "Terrain35": "Valley of Loren", "Terrain36": "Land of Trial",
    "Terrain37": "Aida", "Terrain38": "Crywolf", "Terrain39": "Kanturu",
    "Terrain40": "Lorencia Castle", "Terrain41": "Duel Arena",
    "Terrain42": "Doppel", "Terrain43": "Imperial", "Terrain44": "Illusion Temple",
    "Terrain46": "Raklion", "Terrain47": "Santa", "Terrain51": "Swamp",
    "Terrain52": "Forgotten", "Terrain53": "Forgotten2", "Terrain54": "Forgotten3",
    "Terrain55": "Forgotten4", "Terrain56": "Forgotten5", "Terrain57": "Forgotten6",
    "Terrain58": "Forgotten7", "Terrain59": "Forgotten8", "Terrain61": "Gaion",
    "Terrain62": "Nars", "Terrain63": "Archangel", "Terrain64": "Dungeon2",
    "Terrain65": "Acheron", "Terrain66": "Chaos", "Terrain67": "Panda",
    "Terrain68": "Deep", "Terrain69": "Karutan", "Terrain70": "Dino",
    "Terrain71": "Hell", "Terrain72": "Vulcan", "Terrain73": "Torment",
    "Terrain74": "Ferea", "Terrain75": "Nixie", "Terrain78": "Urk",
    "Terrain79": "Kubera", "Terrain80": "Dread", "Terrain81": "Hollow",
    "Terrain82": "Zero", "075_Terrain1": "075 Dungeon", "075_Terrain2": "075 Devias",
    "075_Terrain3": "075 Noria", "075_Terrain4": "075 Lost", "075_Terrain5": "075 Exile",
    "075_Terrain8": "075 Tarkan",
}

# Gom nhom cho de xem
def group_of(name):
    if name.startswith("075_"):
        return "075 Custom"
    if name.startswith("Terrain3") and ("_" in name or name == "Terrain35"):
        return "Kalima / Loren"
    if name.startswith("Terrain4"):
        return "Castle / Event"
    if name.startswith("Terrain5") or name.startswith("Terrain6") or name.startswith("Terrain7"):
        return "Forgotten / Atlans"
    if name.startswith("Terrain8"):
        return "Special"
    n = name.replace("Terrain", "")
    try:
        num = int("".join(ch for ch in n if ch.isdigit()))
    except ValueError:
        return "Other"
    if num <= 12:
        return "Co ban (0-12)"
    if 19 <= num <= 39:
        return "Kalima / Crywolf (19-39)"
    if 40 <= num <= 47:
        return "Castle / Event (40-47)"
    if 51 <= num <= 59:
        return "Forgotten (51-59)"
    if 61 <= num <= 82:
        return "Season map (61-82)"
    return "Other"

items = []
for att in sorted(glob.glob(os.path.join(SAMPLES, "*.att"))):
    base = os.path.basename(att)
    name = base.rsplit(".", 1)[0]
    png = base + ".png"
    pngp = os.path.join(SAMPLES, png)
    if not os.path.exists(pngp):
        continue
    raw = open(att, "rb").read()
    attrs = v.parse(raw)
    st = v.stats(attrs)
    tot = sum(st.values())
    pct = {k: round(100 * st[k] / tot) for k in st}
    label = MAP_NAMES.get(name, "")
    items.append({
        "file": png, "name": name, "label": label,
        "group": group_of(name), "pct": pct,
    })

# Nhom
groups = {}
for it in items:
    groups.setdefault(it["group"], []).append(it)

order = ["Co ban (0-12)", "Kalima / Loren", "Kalima / Crywolf (19-39)",
         "Castle / Event (40-47)", "Forgotten / Atlans", "Forgotten (51-59)",
         "Season map (61-82)", "Special", "075 Custom", "Other"]

html = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MU .att Gallery (76 map)</title>
<style>
 body{background:#0f1115;color:#e6e6e6;font:14px/1.5 system-ui,sans-serif;margin:0;padding:20px}
 h1{font-size:20px;margin:0 0 4px}
 p.sub{color:#9aa;margin:0 0 16px}
 .legend{display:flex;gap:14px;flex-wrap:wrap;margin:0 0 18px;font-size:12px}
 .legend span{display:flex;align-items:center;gap:6px}
 .sw{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid #333}
 .grp{margin:22px 0 8px;font-size:15px;font-weight:600;color:#8fd}
 .row{display:flex;gap:14px;flex-wrap:wrap}
 .card{background:#171a21;border:1px solid #262b36;border-radius:8px;padding:10px;width:150px}
 .card h3{margin:0 0 6px;font-size:13px}
 .card .lbl{color:#9aa;font-size:11px;margin-bottom:6px;min-height:14px}
 canvas{image-rendering:pixelated;width:128px;height:128px;border:1px solid #333;display:block;cursor:crosshair}
 .meta{color:#9aa;font-size:11px;margin-top:6px;line-height:1.4}
 #tip{position:fixed;background:#000c;padding:4px 8px;border-radius:4px;font-size:12px;pointer-events:none;display:none;z-index:9}
 .bar{height:5px;border-radius:3px;margin-top:5px;background:linear-gradient(90deg,#000 0%,#000 var(--w),#fff var(--w),#fff calc(var(--w) + var(--b)),#2c2c2c calc(var(--w) + var(--b)))}
</style></head><body>
<h1>MU Online — 76 bản đồ đi được (.att)</h1>
<p class="sub">Nguồn: OpenMU <code>TerrainX.att</code> (bản rõ). Màu: đen=đi được, trắng=tường, xanh=safe, xanh dương=nước/vực.</p>
<div class="legend">
 <span><i class="sw" style="background:#000"></i>Đi được</span>
 <span><i class="sw" style="background:#fff"></i>Tường</span>
 <span><i class="sw" style="background:#00b400"></i>Safe</span>
 <span><i class="sw" style="background:#0078ff"></i>Nước/Vực</span>
 <span><i class="sw" style="background:#ff00ff"></i>Khác</span>
</div>
<div id="tip"></div>
"""

for g in order:
    if g not in groups:
        continue
    html += f'<div class="grp">{g} ({len(groups[g])})</div>\n<div class="row">\n'
    for it in groups[g]:
        p = it["pct"]
        w = p.get("walk", 0); b = p.get("block", 0)
        metas = []
        if p.get("safe"): metas.append(f"safe {p['safe']}%")
        if p.get("noground"): metas.append(f"vực {p['noground']}%")
        if p.get("water"): metas.append(f"nước {p['water']}%")
        meta = f"đi {w}% · tường {b}%" + ((" · " + " · ".join(metas)) if metas else "")
        html += f'''<div class="card">
 <h3>{it['name']}</h3>
 <div class="lbl">{it['label']}</div>
 <canvas data-img="{it['file']}" width="256" height="256"></canvas>
 <div class="bar" style="--w:{w}%;--b:{b}%"></div>
 <div class="meta">{meta}</div>
</div>
'''
    html += "</div>\n"

html += """
<script>
const tip=document.getElementById('tip');
document.querySelectorAll('canvas[data-img]').forEach(cv=>{
  const ctx=cv.getContext('2d');
  const img=new Image();
  img.onload=()=>ctx.drawImage(img,0,0);
  img.src=cv.dataset.img;
  cv.addEventListener('mousemove',e=>{
    const r=cv.getBoundingClientRect();
    const x=Math.floor((e.clientX-r.left)/r.width*256);
    const y=Math.floor((e.clientY-r.top)/r.height*256);
    tip.style.display='block';
    tip.style.left=(e.clientX+12)+'px';
    tip.style.top=(e.clientY+12)+'px';
    tip.textContent=cv.dataset.img.replace('.att.png','')+'  ('+x+', '+y+')';
  });
  cv.addEventListener('mouseleave',()=>tip.style.display='none');
});
</script>
</body></html>"""

out = os.path.join(SAMPLES, "att_gallery.html")
open(out, "w", encoding="utf-8").write(html)
print(f"Da sinh {out} voi {len(items)} map, {len(groups)} nhom.")
