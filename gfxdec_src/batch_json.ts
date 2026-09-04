// batch_json.ts - Decode EVERY WorldN/EncTerrain*.att into grid JSON.
// Uses the FULL crypto engine (all 8 Modulus algorithms), unlike att_dec.js.
// Output: att_samples/_grid_cache/WorldN.json + att_samples/WorldN/grid.json
import { readATT } from './terrain/formats/ATTReader.ts';
import * as fs from 'fs';
import * as path from 'path';

const base = '../att_samples';
const cacheDir = path.join(base, '_grid_cache');
fs.mkdirSync(cacheDir, { recursive: true });

const worldDirs = fs.readdirSync(base).filter(d => /^World\d+$/.test(d)).sort();
let ok = 0, fail = 0;

for (const wd of worldDirs) {
  const p = path.join(base, wd);
  const m = parseInt(wd.slice(5), 10);
  // priority file picker: prefer the "_" variant (known-good for some maps)
  const cands = [
    path.join(p, `EncTerrain${m}_.att`),
    path.join(p, `EncTerrain${m}.att`),
    path.join(p, 'EncTerrain.att'),
  ];
  let src = cands.find(c => fs.existsSync(c));
  if (!src) {
    const atts = fs.readdirSync(p).filter(f => f.toLowerCase().endsWith('.att'));
    if (atts.length) src = path.join(p, atts[0]);
  }
  if (!src) { console.log(`SKIP ${wd}: no .att`); fail++; continue; }
  try {
    const buf = fs.readFileSync(src);
    const r = readATT(buf.buffer);
    const grid = Array.from(r.terrainWall);
    const json = JSON.stringify({ index: r.index, isExt: r.isExtended, grid });
    const cachePath = path.join(cacheDir, `World${m}.json`);
    fs.writeFileSync(cachePath, json);
    fs.writeFileSync(path.join(p, 'grid.json'), json);
    const walk = grid.filter(v => (v & (0x0004 | 0x0008 | 0x0010)) === 0).length;
    console.log(`OK ${wd} (${path.basename(src)}): idx=${r.index} ext=${r.isExtended} walk=${walk}/65536`);
    ok++;
  } catch (e: any) {
    console.log(`FAIL ${wd} (${path.basename(src)}): ${e.message}`);
    fail++;
  }
}
console.log(`\nDone: ${ok} ok, ${fail} fail (of ${worldDirs.length} World dirs)`);
