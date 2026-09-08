const path = require('node:path');
const fs = require('node:fs/promises');
const sharp = require('sharp');
(async () => {
  const root = path.resolve(__dirname, '..');
  const source = path.join(root, 'assets', 'creator-radar.svg');
  const sizes = [16, 24, 32, 48, 64, 128, 256];
  const frames = await Promise.all(sizes.map(size => sharp(source).resize(size, size).png().toBuffer()));
  const header = Buffer.alloc(6 + sizes.length * 16);
  header.writeUInt16LE(1, 2); header.writeUInt16LE(sizes.length, 4);
  let offset = header.length;
  frames.forEach((frame, index) => {
    const entry = 6 + index * 16;
    header[entry] = sizes[index] === 256 ? 0 : sizes[index];
    header[entry + 1] = header[entry];
    header.writeUInt16LE(1, entry + 4); header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(frame.length, entry + 8); header.writeUInt32LE(offset, entry + 12);
    offset += frame.length;
  });
  await fs.writeFile(path.join(root, 'assets', 'creator-radar.ico'), Buffer.concat([header, ...frames]));
  await fs.writeFile(path.join(root, 'assets', 'creator-radar.png'), frames[frames.length - 1]);
  console.log('Created seven-resolution desktop icon.');
})().catch(error => { console.error(error.message); process.exitCode = 1; });
