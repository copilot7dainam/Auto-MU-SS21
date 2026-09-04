import { readATT } from './terrain/formats/ATTReader.ts';
import * as fs from 'fs';
const buf = fs.readFileSync('../att_samples/World10/EncTerrain10.att');
const r = readATT(buf.buffer);
console.log('index',r.index,'ext',r.isExtended,'tiles',r.terrainWall.length,'first',Array.from(r.terrainWall.slice(0,10)));
