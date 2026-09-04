import { decryptModulusCryptor } from './crypto/modulus-cryptor.ts';
import { xorBuxMask } from './crypto/file-cryptor.ts';
import * as fs from 'fs';

const raw = Buffer.from(fs.readFileSync('../att_samples/World67/EncTerrain67.att'));
for (const s of [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40]) {
  const buf = Buffer.from(raw.subarray(s));
  try {
    let u8 = decryptModulusCryptor(new Uint8Array(buf));
    u8 = xorBuxMask(u8);
    const isExt = u8.length === 256 * 256 * 2 + 4;
    const isStd = u8.length === 256 * 256 + 4;
    if ((isExt || isStd) && u8[0] === 0) {
      console.log('SHIFT', s, '=> ver', u8[0], 'idx', u8[1], 'w', u8[2], 'h', u8[3], 'EXT', isExt, 'LEN', u8.length);
    } else {
      console.log('shift', s, 'len', u8.length, 'ver', u8[0], 'idx', u8[1], 'w', u8[2], 'h', u8[3]);
    }
  } catch (e: any) {
    console.log('shift', s, 'ERR', e.message);
  }
}
