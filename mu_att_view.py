"""
MU ATT VIEWER - doc file .att (terrain attribute) -> xuat PNG walkable.

Chay: python mu_att_view.py <file.att> [ten_out.png]
  Hoac khong tham so de xem danh sach mau co san trong att_samples/.

Cau truc file .att (OpenMU / S6 - ban ro, 1 byte/ô):
  - 3 byte header
  - 256*256 = 65536 byte, moi byte = thuoc tinh 1 o tile (x,y)
  Bit quan trong (theo OpenMU TerrainAttribute):
    0  = Walkable         (di duoc)
    1  = Blocked          (tuong / vat the)
    2  = SafeZone         (vung an toan)
    3  = Castle
    4  = CastleWall
    5  = Gate
    6  = Water
    7  = Objective (event)

Luu y: file client EncTerrain*.att cua Webzen bi MA HOA (xor_table_3byte).
File OpenMU (TerrainX.att) la ban RO, doc truc tiep duoc. De xem file
client S21 can giai ma truoc (xem ham decrypt_enc() o duoi, thu nghiem).
"""
import sys, os, struct

HEADER = 3
GRID = 256
SIZE = GRID * GRID  # 65536

# Ten goi y map OpenMU (chi de hien thi)
MAP_NAMES = {
    "Terrain0": "Lorencia", "Terrain1": "Dungeon",
    "Terrain2": "Devias", "Terrain3": "Noria",
    "Terrain4": "LostTower", "Terrain5": "Exile",
    "Terrain6": "Arena", "Terrain7": "Atlans",
    "Terrain8": "Tarkan", "Terrain9": "DevilSquare",
    "Terrain10": "Icarus", "Terrain11": "BloodCastle",
}

# Theo OpenMU TerrainAttributeType:
#   0x01 Safezone | 0x02 Character | 0x04 Blocked | 0x08 NoGround | 0x10 Water
# Di duoc = KHONG co bit Blocked/NoGround/Water. 0x00 = dat binh thuong (di duoc).
# Mau pixel: (R,G,B) cho tung loai
COLORS = {
    "walk":   (0, 0, 0),        # den  : di duoc (0x00, 0x01, 0x02)
    "safe":   (0, 180, 0),      # xanh : safe zone (0x01)
    "block":  (255, 255, 255),  # trang: tuong (0x04)
    "noground": (120, 120, 120),# xam  : vuc (0x08)
    "water":  (0, 120, 255),    # xanh nuoc (0x10)
    "other":  (255, 0, 255),    # hong : la (khong thuoc 5 loai tren)
}


def parse(data):
    """Tra ve list 65536 byte thuoc tinh (bo 3 byte header)."""
    if len(data) < HEADER + SIZE:
        raise ValueError(f"File qua nho: {len(data)} byte (can {HEADER+SIZE})")
    return data[HEADER:HEADER + SIZE]


def classify(b):
    """Phan loai 1 byte thanh ten mau (OpenMU TerrainAttributeType)."""
    if b & 0x10:
        return "water"      # Water
    if b & 0x08:
        return "noground"   # NoGround (vuc)
    if b & 0x04:
        return "block"      # Blocked (tuong)
    if b & 0x01:
        return "safe"       # Safezone (van di duoc, nhung to mau rieng)
    if b & 0x02:
        return "walk"       # Character-occupied (di duoc)
    if b == 0:
        return "walk"       # dat binh thuong
    return "other"


def to_png(attrs, out_path):
    try:
        from PIL import Image
    except ImportError:
        # Fallback: ghi PPM (mo duoc bang nhieu viewer, hoac convert sau)
        ppm = out_path.rsplit(".", 1)[0] + ".ppm"
        with open(ppm, "wb") as f:
            f.write(f"P6\n{GRID} {GRID}\n255\n".encode())
            for b in attrs:
                f.write(bytes(COLORS[classify(b)]))
        print(f"  (khong co PIL) ghi {ppm}")
        return ppm
    img = Image.new("RGB", (GRID, GRID))
    px = img.load()
    for i, b in enumerate(attrs):
        y, x = divmod(i, GRID)
        px[x, y] = COLORS[classify(b)]
    img.save(out_path)
    return out_path


def stats(attrs):
    from collections import Counter
    c = Counter(classify(b) for b in attrs)
    return c


def decrypt_enc(data):
    """Thu nghiem giai ma EncTerrain*.att client Webzen (S6+).
    XOR voi bang 3 byte lap lai. Tra ve bytes (co the van sai voi S21).
    Bang: xor_table_3byte = {0xFC, 0xCF, 0xAB} (tu source Balgas/xulek)."""
    key = bytes([0xFC, 0xCF, 0xAB])
    return bytes(data[i] ^ key[i % 3] for i in range(len(data)))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    samples = os.path.join(here, "att_samples")

    if len(sys.argv) >= 2:
        path = sys.argv[1]
        if not os.path.isabs(path):
            path = os.path.join(here, path)
        out = sys.argv[2] if len(sys.argv) >= 3 else path + ".png"
        files = [(path, out)]
    else:
        if not os.path.isdir(samples):
            print("Khong co att_samples/ va khong truyen file.")
            return
        fs = sorted(f for f in os.listdir(samples) if f.endswith(".att"))
        if not fs:
            print("att_samples/ rong.")
            return
        print("Mau co san:")
        for f in fs:
            base = f.rsplit(".", 1)[0]
            print(f"  {f:18s} <- {MAP_NAMES.get(base, '?')}")
        print("\nChay: python mu_att_view.py att_samples/Terrain1.att")
        return

    for path, out in files:
        print(f"Doc {path} ...")
        raw = open(path, "rb").read()
        name = os.path.basename(path)
        base = name.rsplit(".", 1)[0]

        # Neu la file client ma hoa (Enc...), thu giai ma
        if name.lower().startswith("enc") and raw[:3] != b"\x00\xff\xff":
            print("  phat hien giong file ma hoa -> thu giai ma XOR 3-byte")
            raw = decrypt_enc(raw)

        attrs = parse(raw)
        outp = to_png(attrs, out)
        st = stats(attrs)
        label = MAP_NAMES.get(base, base)
        print(f"  [{label}] {outp}")
        tot = sum(st.values())
        for k in ("walk", "safe", "block", "noground", "water", "other"):
            if st[k]:
                print(f"     {k:9s}: {st[k]:5d}  ({100*st[k]/tot:5.1f}%)")


if __name__ == "__main__":
    main()
