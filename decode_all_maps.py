"""
Giai ma TOAN BO map: voi moi thu muc WorldN, decode file .att uu tien
(EncTerrainN.att -> EncTerrain.att -> .att dau tien) thanh grid JSON.

Ket qua:
  - att_samples/_grid_cache/WorldN.json   (de mu_path.load_grid doc truc tiep)
  - att_samples/WorldN/grid.json          (ban sao de xem/luu tru tung World)

Chay: python decode_all_maps.py
"""
import os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mu_path

HERE = os.path.dirname(os.path.abspath(__file__))
ATT = os.path.join(HERE, "att_samples")
CACHE = os.path.join(ATT, "_grid_cache")
os.makedirs(CACHE, exist_ok=True)

world_dirs = sorted(
    d for d in os.listdir(ATT)
    if re.fullmatch(r"World\d+", d)
)
print(f"Tim thay {len(world_dirs)} thu muc World.")

ok = 0
fail = []
for d in world_dirs:
    m = int(re.fullmatch(r"World(\d+)", d).group(1))
    try:
        walk, ext = mu_path.load_grid(m, force=True)  # ghi _grid_cache/WorldN.json
    except Exception as e:
        fail.append((d, str(e)[:120]))
        print(f"  [SKIP] {d}: {e}")
        continue
    src = os.path.join(CACHE, f"World{m}.json")
    dst = os.path.join(ATT, d, "grid.json")
    shutil.copyfile(src, dst)
    nw = sum(sum(r) for r in walk)
    ok += 1
    print(f"  [OK] {d}: ext={ext}, walkable={nw}/65536")

print(f"\nHoan tat: {ok} thanh cong, {len(fail)} loi.")
if fail:
    print("Cac map loi:")
    for d, e in fail:
        print(f"  {d}: {e}")
