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


def load_grid(map_num, force=False):
    """Tra ve (grid2d, is_ext) voi grid2d[y][x] = bool walkable."""
    cache = os.path.join(CACHE, f"World{map_num}.json")
    if force or not os.path.exists(cache):
        cache = _decode_att(map_num)
    d = json.load(open(cache))
    g = d["grid"]
    walk = [[False] * N for _ in range(N)]
    for i, v in enumerate(g):
        y, x = divmod(i, N)
        walk[y][x] = (int(v) & BLOCK) == 0
    return walk, d.get("isExt", False)


def astar(walk, start, goal):
    """A* tren grid 256x256. start/goal = (x,y) tile. Tra ve list[(x,y)] (ke ca goal)."""
    def h(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
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


def coord_to_tile(x, y):
    return (int(round(x)) % N, int(round(y)) % N)


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
