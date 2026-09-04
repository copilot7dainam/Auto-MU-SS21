import { readATT } from './terrain/formats/ATTReader.ts';
import * as fs from 'fs';
import * as path from 'path';
import zlib from 'zlib';

const base = '../att_samples';

// ANSI colors for PWR flags (OpenMU-like): black=walk, white=block, etc.
function classify(v: number): [number, number, number] {
  // v is 16-bit flags. Walkable if none of NoMove/NoGround/Water set.
  const NoMove = 0x0004, NoGround = 0x0008, Water = 0x0010, Safe = 0x0001;
  if (v & Water) return [0, 120, 255];
  if (v & NoGround) return [120, 120, 120];
  if (v & NoMove) return [255, 255, 255];
  if (v & Safe) return [0, 180, 0];
  return [0, 0, 0]; // walkable
}

function writePNG(file: string, grid: Uint16Array, isExt: boolean) {
  const N = 256;
  const px = Buffer.alloc(N * N * 3);
  for (let i = 0; i < N * N; i++) {
    const [r, g, b] = classify(grid[i]);
    px[i * 3] = r; px[i * 3 + 1] = g; px[i * 3 + 2] = b;
  }
  // minimal PNG writer (truecolor)
  const raw = Buffer.alloc(N * N * 3 + N);
  for (let y = 0; y < N; y++) {
    raw[y * (N * 3 + 1)] = 0;
    px.copy(raw, y * (N * 3 + 1) + 1, y * N * 3, y * N * 3 + N * 3);
  }
  const idat = zlib.deflateSync(raw);
  function chunk(type: string, data: Buffer): Buffer {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
    const t = Buffer.from(type, 'ascii');
    const crc = Buffer.alloc(4);
    const c = zlib.crc32 ? zlib.crc32(Buffer.concat([t, data])) : 0;
    crc.writeUInt32BE(c >>> 0, 0);
    return Buffer.concat([len, t, data, crc]);
  }
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(N, 0); ihdr.writeUInt32BE(N, 4);
  ihdr[8] = 8; ihdr[9] = 2; // 8-bit, truecolor
  const png = Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))]);
  fs.writeFileSync(file, png);
}

let count = 0;
for (const wd of fs.readdirSync(base)) {
  const p = path.join(base, wd);
  if (!fs.statSync(p).isDirectory()) continue;
  for (const f of fs.readdirSync(p)) {
    if (!/EncTerrain.*\.att$/i.test(f)) continue;
    const fp = path.join(p, f);
    try {
      const buf = fs.readFileSync(fp);
      const r = readATT(buf.buffer);
      const outName = f + '.png';
      writePNG(path.join(p, outName), r.terrainWall, r.isExtended);
      count++;
      console.log(`OK ${fp} -> ${outName} idx=${r.index} ext=${r.isExtended}`);
    } catch (e: any) {
      console.log(`FAIL ${fp}: ${e.message}`);
    }
  }
}
console.log(`\nDone: ${count} files`);
