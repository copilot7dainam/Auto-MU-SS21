// att_dec.js - Giai ma EncTerrain*.att client MU (S21) bang JS thuan.
// Dich tu xulek/muonline-bmd-viewer (TS) -> JS. Chay: node att_dec.js <file.att> [out.bin]

function rotl32(x, n) { return ((x << n) | (x >>> (32 - n))) >>> 0; }
function rotr32(x, n) { return ((x >>> n) | (x << (32 - n))) >>> 0; }
function mul32(a, b) { return Math.imul(a, b) >>> 0; }

// ---- TEA (algo 0) ----
class TEACipher {
  constructor(key) {
    this.k = new Uint32Array(4);
    for (let i = 0; i < 4; i++)
      this.k[i] = (key[4*i]<<24 | key[4*i+1]<<16 | key[4*i+2]<<8 | key[4*i+3]) >>> 0;
    this.BS = 8; this.DELTA = 0x9E3779B9; this.ROUNDS = 32;
  }
  getBlockSize(){return this.BS;}
  blockDecrypt(inBuf, len, outBuf) {
    for (let i=0;i<len;i+=this.BS) this._dec(inBuf,i,outBuf,i);
  }
  _dec(s,o,d,od){
    let v0=(s[o]<<24|s[o+1]<<16|s[o+2]<<8|s[o+3])>>>0;
    let v1=(s[o+4]<<24|s[o+5]<<16|s[o+6]<<8|s[o+7])>>>0;
    const k0=this.k[0],k1=this.k[1],k2=this.k[2],k3=this.k[3];
    let sum=(mul32(this.DELTA,this.ROUNDS))>>>0;
    for(let i=0;i<this.ROUNDS;i++){
      v1=(v1-(((v0<<4)+k2)^ (v0+sum)^ ((v0>>>5)+k3)))>>>0;
      v0=(v0-(((v1<<4)+k0)^ (v1+sum)^ ((v1>>>5)+k1)))>>>0;
      sum=(sum-this.DELTA)>>>0;
    }
    d[od]=v0>>>24;d[od+1]=v0>>>16&255;d[od+2]=v0>>>8&255;d[od+3]=v0&255;
    d[od+4]=v1>>>24;d[od+5]=v1>>>16&255;d[od+6]=v1>>>8&255;d[od+7]=v1&255;
  }
}

// ---- ThreeWay (algo 1) ----
function revBytes(x){return (((x&0xff)<<24)|((x&0xff00)<<8)|((x&0xff0000)>>>8)|((x&0xff000000)>>>24))>>>0;}
function revBits(a){a=(((a&0xAAAAAAAA)>>>1)|((a&0x55555555)<<1))>>>0;a=(((a&0xCCCCCCCC)>>>2)|((a&0x33333333)<<2))>>>0;return (((a&0xF0F0F0F0)>>>4)|((a&0x0F0F0F0F)<<4))>>>0;}
function theta(t){const c0=(t.a0^t.a1^t.a2)>>>0;const c=(rotl32(c0,16)^rotl32(c0,8))>>>0;const b0=(((t.a0<<24)^(t.a2>>>8)^(t.a1<<8)^(t.a0>>>24))>>>0);const b1=(((t.a1<<24)^(t.a0>>>8)^(t.a2<<8)^(t.a1>>>24))>>>0);t.a0=(t.a0^c^b0)>>>0;t.a1=(t.a1^c^b1)>>>0;t.a2=(t.a2^c^((b0>>>16)^(b1<<16)))>>>0;}
function mu(t){t.a1=revBits(t.a1);const tmp=revBits(t.a0);t.a0=revBits(t.a2);t.a2=tmp;}
function piGammaPi(t){const b2=rotl32(t.a2,1);const b0=rotl32(t.a0,22);t.a0=rotl32((b0^(t.a1|(~b2>>>0)))>>>0,1);t.a2=rotl32((b2^(b0|(~t.a1>>>0)))>>>0,22);t.a1=(t.a1^(b2|(~b0>>>0)))>>>0;}
function rho(t){theta(t);piGammaPi(t);}
class ThreeWayCipher{
  constructor(key){
    this.k=new Uint32Array(3);this.BS=12;this.ROUNDS=11;this.START_D=0xB1B1;
    for(let i=0;i<3;i++)this.k[i]=((key[4*i+3])|(key[4*i+2]<<8)|(key[4*i+1]<<16)|(key[4*i]<<24))>>>0;
    const tk={a0:this.k[0],a1:this.k[1],a2:this.k[2]};theta(tk);mu(tk);
    this.k[0]=revBytes(tk.a0);this.k[1]=revBytes(tk.a1);this.k[2]=revBytes(tk.a2);
  }
  getBlockSize(){return this.BS;}
  blockDecrypt(inBuf,len,outBuf){for(let i=0;i<len;i+=this.BS)this._dec(inBuf,i,outBuf,i);}
  _dec(s,o,d,od){
    const t={a0:(s[o]<<24|s[o+1]<<16|s[o+2]<<8|s[o+3])>>>0,
             a1:(s[o+4]<<24|s[o+5]<<16|s[o+6]<<8|s[o+7])>>>0,
             a2:(s[o+8]<<24|s[o+9]<<16|s[o+10]<<8|s[o+11])>>>0};
    let rc=this.START_D;mu(t);
    for(let i=0;i<this.ROUNDS;i++){
      t.a0=(t.a0^this.k[0]^(rc<<16))>>>0;t.a1=(t.a1^this.k[1])>>>0;t.a2=(t.a2^this.k[2]^rc)>>>0;
      rho(t);rc=(rc<<1)>>>0;if(rc&0x10000)rc^=0x11011;rc&=0xFFFF;
    }
    t.a0=(t.a0^this.k[0]^(rc<<16))>>>0;t.a1=(t.a1^this.k[1])>>>0;t.a2=(t.a2^this.k[2]^rc)>>>0;
    theta(t);mu(t);
    d[od]=t.a0>>>24;d[od+1]=t.a0>>>16&255;d[od+2]=t.a0>>>8&255;d[od+3]=t.a0&255;
    d[od+4]=t.a1>>>24;d[od+5]=t.a1>>>16&255;d[od+6]=t.a1>>>8&255;d[od+7]=t.a1&255;
    d[od+8]=t.a2>>>24;d[od+9]=t.a2>>>16&255;d[od+10]=t.a2>>>8&255;d[od+11]=t.a2&255;
  }
}

// ---- RC6 (algo 4) ----
function _rotl(x,n){n&=31;return ((x<<n)|(x>>>(32-n)))>>>0;}
function _rotr(x,n){n&=31;return ((x>>>n)|(x<<(32-n)))>>>0;}
function _mul(a,b){return Math.imul(a,b)>>>0;}
class RC6Cipher{
  constructor(key){
    this.BS=16;this.r=20;this.P32=0xB7E15163;this.Q32=0x9E3779B9;
    const k=key.slice(0,16);
    const c=Math.max(Math.floor(k.length/4),1);
    const L=new Uint32Array(c);
    for(let i=k.length-1;i>=0;i--) L[Math.floor(i/4)]=((L[Math.floor(i/4)]<<8)+k[i])>>>0;
    const sLen=2*this.r+4;
    const S=new Uint32Array(sLen);
    S[0]=this.P32;
    for(let i=1;i<sLen;i++) S[i]=(S[i-1]+this.Q32)>>>0;
    let A=0,B=0,ii=0,jj=0;
    const v=3*Math.max(sLen,c);
    for(let s=0;s<v;s++){
      A=(S[ii]+(A+B))>>>0; A=_rotl(A,3); S[ii]=A;
      B=(L[jj]+(A+B))>>>0; B=_rotl(B,(A+B)&31); L[jj]=B;
      ii=(ii+1)%sLen; jj=(jj+1)%c;
    }
    this.S=S;
  }
  getBlockSize(){return this.BS;}
  blockDecrypt(inBuf,len,outBuf){for(let i=0;i<len;i+=this.BS)this._dec(inBuf,i,outBuf,i);}
  _dec(s,o,d,od){
    const S=this.S,r=this.r;
    let A=((s[o]<<24)|(s[o+1]<<16)|(s[o+2]<<8)|s[o+3])>>>0;
    let B=((s[o+4]<<24)|(s[o+5]<<16)|(s[o+6]<<8)|s[o+7])>>>0;
    let C=((s[o+8]<<24)|(s[o+9]<<16)|(s[o+10]<<8)|s[o+11])>>>0;
    let D=((s[o+12]<<24)|(s[o+13]<<16)|(s[o+14]<<8)|s[o+15])>>>0;
    A=(A-S[2*r+2])>>>0;
    C=(C-S[2*r+3])>>>0;
    for(let i=r;i>=1;i--){
      const t=D; D=C; C=B; B=A; A=t;
      const u=_rotl(_mul(D,(2*D+1)>>>0),5);
      const v=_rotl(_mul(B,(2*B+1)>>>0),5);
      C=((_rotr((C-S[2*i+1])>>>0, v&31))^u)>>>0;
      A=((_rotr((A-S[2*i])>>>0, u&31))^v)>>>0;
    }
    B=(B-S[0])>>>0;
    D=(D-S[1])>>>0;
    d[od]=A>>>24;d[od+1]=A>>>16&255;d[od+2]=A>>>8&255;d[od+3]=A&255;
    d[od+4]=B>>>24;d[od+5]=B>>>16&255;d[od+6]=B>>>8&255;d[od+7]=B&255;
    d[od+8]=C>>>24;d[od+9]=C>>>16&255;d[od+10]=C>>>8&255;d[od+11]=C&255;
    d[od+12]=D>>>24;d[od+13]=D>>>16&255;d[od+14]=D>>>8&255;d[od+15]=D&255;
  }
}

const CIPHERS={0:TEACipher,1:ThreeWayCipher,4:RC6Cipher};
const CNAME={0:'TEA',1:'ThreeWay',4:'RC6'};
const KEY1=new Uint8Array('webzen#@!01webzen#@!01webzen#@!0'.split('').map(c=>c.charCodeAt(0))); // 32 bytes

function decryptModulus(buf){
  if(buf.length<34) throw new Error('too short');
  const algorithm1=buf[1], algorithm2=buf[0];
  const size=buf.length, dataSize=size-34;
  const c1=CIPHERS[algorithm1&7]; if(!c1) throw new Error('algo1 unsupported '+(algorithm1&7));
  const cipher1=new c1(KEY1);
  const blockSize=1024-(1024%cipher1.getBlockSize());
  if(dataSize>4*blockSize){let idx=2+(dataSize>>>1);const b=buf.slice(idx,idx+blockSize);cipher1.blockDecrypt(b,b.length,b);buf.set(b,idx);}
  if(dataSize>blockSize){
    let idx=size-blockSize;let b=buf.slice(idx,idx+blockSize);cipher1.blockDecrypt(b,b.length,b);buf.set(b,idx);
    idx=2;b=buf.slice(idx,idx+blockSize);cipher1.blockDecrypt(b,b.length,b);buf.set(b,idx);
  }
  const key2=buf.slice(2,34);
  const c2=CIPHERS[algorithm2&7]; if(!c2) throw new Error('algo2 unsupported '+(algorithm2&7));
  const cipher2=new c2(key2);
  const decSize=dataSize-(dataSize%cipher2.getBlockSize());
  if(decSize>0){const b=buf.slice(34,34+decSize);cipher2.blockDecrypt(b,b.length,b);buf.set(b,34);}
  return {result:buf.slice(34),algo1:algorithm1&7,algo2:algorithm2&7};
}

const MAP_KEY=new Uint8Array([0xD1,0x73,0x52,0xF6,0xD2,0x9A,0xCB,0x27,0x3E,0xAF,0x59,0x31,0x37,0xB3,0xE7,0xA2]);
const BUX=new Uint8Array([0xFC,0xCF,0xAB]);
function decryptFileCryptor(src){
  const dst=Buffer.alloc(src.length);let mk=0x5E;
  for(let i=0;i<src.length;i++){dst[i]=((src[i]^MAP_KEY[i&15])-mk)&0xFF;mk=(src[i]+0x3D)&0xFF;}
  return dst;
}
function xorBux(b){const o=Buffer.alloc(b.length);for(let i=0;i<b.length;i++)o[i]=b[i]^BUX[i%3];return o;}

function readATT(buffer){
  let u8=Buffer.from(buffer);
  let usedModulus=false;
  if(u8.length>4 && u8[0]===0x41 && u8[1]===0x54 && u8[2]===0x54 && u8[3]===1){
    const r=decryptModulus(u8.slice(4)); u8=r.result; usedModulus=true;
  } else {
    u8=decryptFileCryptor(u8);
  }
  u8=xorBux(u8);
  const expectedStd=256*256+4, expectedExt=256*256*2+4;
  if(u8.length!==expectedStd && u8.length!==expectedExt) throw new Error('unexpected size '+u8.length);
  const isExt=u8.length===expectedExt;
  const version=u8[0], index=u8[1], width=u8[2], height=u8[3];
  if(version!==0) throw new Error('unsupported version '+version);
  if(width!==255||height!==255) throw new Error('bad dims '+width+'x'+height);
  const grid=[]; let off=4;
  for(let i=0;i<256*256;i++){
    if(isExt){grid.push(u8[off]|(u8[off+1]<<8));off+=2;}
    else{grid.push(u8[off]);off+=1;}
  }
  return {version,index,isExt,grid,usedModulus};
}

// CLI
const fs=require('fs');
if(require.main===module){
  const f=process.argv[2];
  if(!f){console.error('usage: node att_dec.js <file.att> [out.json]');process.exit(1);}
  const buf=fs.readFileSync(f);
  const r=readATT(buf);
  console.log(`file=${f} index=${r.index} ext=${r.isExt} modulus=${r.usedModulus} tiles=${r.grid.length}`);
  console.log('first20 tiles:', r.grid.slice(0,20).join(','));
  if(process.argv[3]){
    fs.writeFileSync(process.argv[3], JSON.stringify({index:r.index,isExt:r.isExt,grid:r.grid}));
  }
}
module.exports={readATT,decryptModulus,decryptFileCryptor,xorBux,RC6Cipher,TEACipher,ThreeWayCipher};
