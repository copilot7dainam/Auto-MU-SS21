"""
MU PATH - A* pathfinding tren luoi walkable S21 (tu file .att da giai ma).

Luong di:
  - load_grid(map_num): lay grid 256x256 walkable cua World<map_num>.
      Thu tu: (1) cache JSON co san, (2) goi node att_dec.js giai ma .att -> JSON.
  - astar(grid, start, goal): tra ve danh sach waypoint (tile x,y) tu start->goal.
  - tile<->coord: MU dung 1 tile = 1 game-unit (apine), nen tile = round(coord).

Phu thuoc: node.exe (de giai ma .att lan dau). Da cache thi khong can.

Chay rieng de test: python mu_path.py <map_num> <sx> <sy> <tx> <ty>
"""
import os, sys, json, subprocess, math

HERE = os.path.dirname(os.path.abspath(__file__))
ATT = os.path.join(HERE, "att_samples")
GFX = os.path.join(HERE, "gfxdec_src")
CACHE = os.path.join(ATT, "_grid_cache")
N = 256

# Flag bit cho biet CHAN (khong di duoc)
BLOCK = 0x0004 | 0x0008 | 0x0010   # NoMove | NoGround | Water

def _decode_att(map_num):
    """Goi node att_dec.js giai ma World<map_num>/EncTerrain<map>.att -> dict."""
    wd = os.path.join(ATT, f"World{map_num}")
    if not os.path.isdir(wd):
        raise FileNotFoundError(f"Khong co thu muc {wd}")
    # tim file .att (uu tien EncTerrain<map_num>.att)
    cand = [
        os.path.join(wd, f"EncTerrain{map_num}.att"),
        os.path.join(wd, "EncTerrain.att"),
    ]
    src = next((c for c in cand if os.path.exists(c)), None)
    if src is None:
        atts = [f for f in os.listdir(wd) if f.lower().endswith(".att")]
        if not atts:
            raise FileNotFoundError(f"Khong co .att trong {wd}")
        src = os.path.join(wd, atts[0])
    out = os.path.join(CACHE, f"World{map_num}.json")
    os.makedirs(CACHE, exist_ok=True)
    r = subprocess.run(
        ["node", os.path.join(GFX, "att_dec.js"), src, out],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"att_dec.js loi: {r.stderr[:300]}")
    return out


def load_grid(map_num, force=False, safe_margin=1, keep_points=None):
    """Tra ve (grid2d, is_ext) voi grid2d[y][x] = bool walkable.
    safe_margin: cach chuong ngai vat toi thieu N tile (mac dinh 1) de tranh bi kem.
    keep_points: cac (x,y) luon giu walkable (vd start/goal cua nhan vat)."""
    cache = os.path.join(CACHE, f"World{map_num}.json")
    if force or not os.path.exists(cache):
        cache = _decode_att(map_num)
    d = json.load(open(cache))
    g = d["grid"]
    walk = [[False] * N for _ in range(N)]
    for i, v in enumerate(g):
        y, x = divmod(i, N)
        walk[y][x] = (int(v) & BLOCK) == 0
    if safe_margin > 0:
        walk = make_safe(walk, safe_margin, keep=keep_points)
    return walk, d.get("isExt", False)


def make_safe(walk, margin=1, keep=None):
    """Tra ve grid moi voi cac o CACH chuong ngai vat 'margin' tile tro len bi loai bo.
    Muc dich: duong di khong sat tuong -> han che bi kem/vuong khi click thuc te.
    O chi di duoc neu no walkable VA khong co o block nao trong ban kinh 'margin'.
    keep: tap cac (x,y) LUON duoc giu walkable (vi du start/goal cua nhan vat)."""
    keep = set(keep or [])
    N = len(walk)
    safe = [[False] * N for _ in range(N)]
    for y in range(N):
        for x in range(N):
            if not walk[y][x]:
                continue
            if (x, y) in keep:
                safe[y][x] = True
                continue
            blocked = False
            for dy in range(-margin, margin + 1):
                for dx in range(-margin, margin + 1):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < N and 0 <= ny < N):
                        continue
                    if not walk[ny][nx]:
                        blocked = True
                        break
                if blocked:
                    break
            safe[y][x] = not blocked
    return safe


def astar(walk, start, goal):
    """A* tren grid 256x256. start/goal = (x,y) tile. Tra ve list[(x,y)] (ke ca goal).
    Dung heuristic octile (admissible cho di chuyen 8 huong, duong cheo = sqrt2) nen
    dam bao tim duoc DUONG NGAN NHAT."""
    def h(a, b):
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)
    def neighbors(x, y):
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < N and 0 <= ny < N and walk[ny][nx]:
                yield (nx, ny), math.hypot(dx, dy)
    sx, sy = start; gx, gy = goal
    if not (0 <= sx < N and 0 <= sy < N and 0 <= gx < N and 0 <= gy < N):
        return None
    if not walk[sy][sx] or not walk[gy][gx]:
        return None
    open_set = {start: (0, h(start, goal))}
    came = {}
    gscore = {start: 0}
    import heapq
    pq = [(h(start, goal), 0, start)]
    while pq:
        f, g, cur = heapq.heappop(pq)
        if cur == goal:
            path = [cur]; c = cur
            while c in came:
                c = came[c]; path.append(c)
            return path[::-1]
        if open_set.get(cur, (1e9, 0))[1] < f:
            continue
        for nb, cost in neighbors(*cur):
            ng = gscore[cur] + cost
            if ng < gscore.get(nb, 1e9):
                came[nb] = cur
                gscore[nb] = ng
                f2 = ng + h(nb, goal)
                open_set[nb] = (ng, f2)
                heapq.heappush(pq, (f2, ng, nb))
    return None


def replan(walk, start, goal, blocked=None, radius=3):
    """Tim duong moi tu start->goal, CO BLOCK TAM THOI cac o quanh vi tri 'blocked'
    (vi tri nhan vat bi kem). radius: ban kinh block them quanh blocked de ep duong
    di VONG qua, khong di lai toa do bi kem. Tra ve list waypoint hoac None."""
    import copy
    w = [row[:] for row in walk]   # sao chep de khong sua grid goc
    if blocked is not None:
        bx, by = blocked
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = bx + dx, by + dy
                if 0 <= nx < N and 0 <= ny < N:
                    w[ny][nx] = False
    # dam bao start/goal van walkable (nhan vat dang o do, va dich co the trong vung)
    sx, sy = start; gx, gy = goal
    if 0 <= sx < N and 0 <= sy < N:
        w[sy][sx] = True
    if 0 <= gx < N and 0 <= gy < N:
        w[gy][gx] = True
    return astar(w, start, goal)


def coord_to_tile(x, y):
    return (int(round(x)) % N, int(round(y)) % N)


def nearest_walkable(walk, tx, ty, max_r=30):
    """Tra ve (x,y) tile walkable gan nhat voi (tx,ty). None neu khong co."""
    if 0 <= tx < N and 0 <= ty < N and walk[ty][tx]:
        return (tx, ty)
    for r in range(1, max_r + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) != r and abs(dy) != r:
                    continue  # chi xet vien hinh vuong ban kinh r
                x, y = tx + dx, ty + dy
                if 0 <= x < N and 0 <= y < N and walk[y][x]:
                    return (x, y)
    return None


def tile_to_coord(tx, ty):
    return float(tx), float(ty)


if __name__ == "__main__":
    if len(sys.argv) >= 6:
        m = int(sys.argv[1]); sx, sy, tx, ty = map(int, sys.argv[2:6])
    else:
        m, sx, sy, tx, ty = 1, 10, 10, 200, 200
    w, ext = load_grid(m)
    print(f"Map {m} (ext={ext}) loaded. start=({sx},{sy}) goal=({tx},{ty})")
    p = astar(w, (sx, sy), (tx, ty))
    if p is None:
        print("Khong tim thay duong.")
    else:
        print(f"Tim thay {len(p)} waypoint:")
        print(p[:10], "..." if len(p) > 10 else "")
