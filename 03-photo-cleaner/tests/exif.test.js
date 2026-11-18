// Usage: node tests/exif.test.js   (from the 03-photo-cleaner folder)
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1].split("// ---------- Processing")[0]
  .replace("const $ = (id) => document.getElementById(id);", "").replace("const items = [];", "");
const { findMetadata } = new Function(script + "\nreturn { findMetadata };")();

function jpegWithExif(little) {
  const w16 = (n) => (little ? [n & 255, n >> 8] : [n >> 8, n & 255]);
  const w32 = (n) => (little ? [n & 255, (n >> 8) & 255, (n >> 16) & 255, n >>> 24] : [n >>> 24, (n >> 16) & 255, (n >> 8) & 255, n & 255]);
  const model = [..."Pixel 7"].map((c) => c.charCodeAt(0)).concat([0]);
  const entries = [
    [...w16(0x0110), ...w16(2), ...w32(8), ...w32(8 + 2 + 3 * 12 + 4)],
    [...w16(0x8825), ...w16(4), ...w32(1), ...w32(0)],
    [...w16(0x0132), ...w16(2), ...w32(4), 50, 50, 50, 0],
  ];
  const ifd = [...w16(3), ...entries.flat(), ...w32(0), ...model];
  const tiff = [...(little ? [0x49, 0x49] : [0x4d, 0x4d]), ...w16(42), ...w32(8), ...ifd];
  const body = [0x45, 0x78, 0x69, 0x66, 0, 0, ...tiff];
  const len = body.length + 2;
  return new Uint8Array([0xff, 0xd8, 0xff, 0xe1, len >> 8, len & 255, ...body, 0xff, 0xda, 0, 2, 0xff, 0xd9]);
}
const fake = (bytes, type = "image/jpeg") => ({ type, slice: () => ({ arrayBuffer: async () => bytes.buffer }) });
const slicedFake = (bytes, type = "image/jpeg") => ({
  type,
  slice: (start, end) => ({ arrayBuffer: async () => bytes.buffer.slice(start, end) }),
});

// A JPEG whose APP1/EXIF segment starts at byte 262139, inside the 256 KB window but
// leaving fewer than 4 bytes after it. Reading the marker used to throw a RangeError.
function jpegWithApp1AtTheEdge() {
  const bytes = new Uint8Array(300000);
  bytes[0] = 0xff;
  bytes[1] = 0xd8;
  let offset = 2;
  for (const size of [65535, 65535, 65535, 65524]) {
    bytes[offset] = 0xff;
    bytes[offset + 1] = 0xe2;  // APP2 filler
    bytes[offset + 2] = size >> 8;
    bytes[offset + 3] = size & 255;
    offset += 2 + size;
  }
  bytes[offset] = 0xff;
  bytes[offset + 1] = 0xe1;  // APP1
  bytes.set([0, 8, 0x45, 0x78, 0x69, 0x66, 0, 0], offset + 2);  // "Exif\0\0"
  return bytes;
}
const assert = (cond, msg) => { if (!cond) { console.error("FAIL:", msg); process.exit(1); } };

(async () => {
  for (const little of [false, true]) {
    const found = await findMetadata(fake(jpegWithExif(little)));
    assert(found.includes("Camera model: Pixel 7"), "model " + little);
    assert(found.includes("GPS location"), "gps " + little);
    assert(found.includes("Date modified"), "date " + little);
  }
  assert((await findMetadata(fake(new Uint8Array([0xff, 0xd8, 0xff, 0xd9, 0, 0])))).length === 0, "jpeg without exif");
  assert((await findMetadata(fake(new Uint8Array(10), "image/png"))).length === 0, "png");
  assert((await findMetadata(slicedFake(jpegWithApp1AtTheEdge()))).length === 0, "APP1 at the edge of the window");
  console.log("EXIF OK");
})();
