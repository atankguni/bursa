#!/usr/bin/env node
/**
 * gen-favicons.mjs
 * ----------------
 * Regenerates the raster favicon assets, deterministically and offline, from
 * the geometry defined below (mirrors `frontend/public/favicon.svg`).
 *
 * Why this exists: the original assets were produced with macOS `qlmanage`,
 * which drew the 64px artwork small inside a larger white canvas, so the badge
 * became a tiny blob in the corner (Chromium, which prefers the .ico, then
 * showed a white square). This script rasterizes the icon to fill each frame,
 * supersampled for anti-aliasing, and packs a proper multi-resolution .ico.
 *
 * No browser or image tooling required — only Node's built-in `zlib`.
 *
 * Outputs (into frontend/public/):
 *   - favicon.ico          (multi-resolution: 16, 32, 48)
 *   - apple-touch-icon.png (180)
 *
 * Usage:  node scripts/gen-favicons.mjs
 */

import { deflateSync } from 'node:zlib'
import { writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC_DIR = resolve(__dirname, '..', 'public')

const ICO_SIZES = [16, 32, 48]
const APPLE_SIZE = 180
const SS = 4 // supersample factor for anti-aliasing

// --------------------------------------------------------------------------- //
// Design (in a 64x64 coordinate space, matching favicon.svg)
// --------------------------------------------------------------------------- //
const GREEN = [22, 163, 74] // #16a34a
const WHITE = [255, 255, 255]

const BADGE = { x: 0, y: 0, w: 64, h: 64, r: 14 }
const CANDLES = [
  { x: 16.9, y: 30, w: 2.2, h: 26, r: 1.1 }, // wick 1
  { x: 14, y: 36, w: 8, h: 14, r: 2 }, // body 1
  { x: 30.9, y: 20, w: 2.2, h: 32, r: 1.1 }, // wick 2
  { x: 28, y: 27, w: 8, h: 16, r: 2 }, // body 2
  { x: 44.9, y: 11, w: 2.2, h: 33, r: 1.1 }, // wick 3
  { x: 42, y: 18, w: 8, h: 18, r: 2 }, // body 3
]

/** Point-in-rounded-rectangle test (px,py in the 64-unit space). */
function inRoundRect(px, py, { x, y, w, h, r }) {
  if (px < x || px > x + w || py < y || py > y + h) return false
  const cx = Math.min(Math.max(px, x + r), x + w - r)
  const cy = Math.min(Math.max(py, y + r), y + h - r)
  const dx = px - cx
  const dy = py - cy
  return dx * dx + dy * dy <= r * r
}

// --------------------------------------------------------------------------- //
// Rasterize one size -> straight-alpha RGBA Buffer
// --------------------------------------------------------------------------- //
function rasterize(size) {
  const hi = size * SS
  const scale = 64 / hi

  // Accumulate supersampled coverage into the target pixels.
  const out = Buffer.alloc(size * size * 4)
  for (let ty = 0; ty < size; ty++) {
    for (let tx = 0; tx < size; tx++) {
      let aSum = 0
      let rSum = 0
      let gSum = 0
      let bSum = 0

      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          const u = (tx * SS + sx + 0.5) * scale
          const v = (ty * SS + sy + 0.5) * scale

          let rgba = null
          if (inRoundRect(u, v, BADGE)) rgba = GREEN
          for (const c of CANDLES) {
            if (inRoundRect(u, v, c)) {
              rgba = WHITE
              break
            }
          }

          if (rgba) {
            aSum += 1
            rSum += rgba[0]
            gSum += rgba[1]
            bSum += rgba[2]
          }
        }
      }

      const n = SS * SS
      const o = (ty * size + tx) * 4
      if (aSum > 0) {
        // Average color over covered samples; straight (non-premultiplied) alpha.
        out[o + 0] = Math.round(rSum / aSum)
        out[o + 1] = Math.round(gSum / aSum)
        out[o + 2] = Math.round(bSum / aSum)
        out[o + 3] = Math.round((aSum / n) * 255)
      }
    }
  }
  return out
}

// --------------------------------------------------------------------------- //
// Minimal PNG encoder (8-bit RGBA, no interlace)
// --------------------------------------------------------------------------- //
const CRC_TABLE = (() => {
  const t = new Uint32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c >>> 0
  }
  return t
})()

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length, 0)
  const typeBuf = Buffer.from(type, 'ascii')
  const body = Buffer.concat([typeBuf, data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body), 0)
  return Buffer.concat([len, body, crc])
}

function encodePng(width, height, rgba) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // color type: RGBA
  ihdr[10] = 0 // compression
  ihdr[11] = 0 // filter
  ihdr[12] = 0 // interlace

  // Prepend a filter byte (0 = None) to each scanline.
  const stride = width * 4
  const raw = Buffer.alloc((stride + 1) * height)
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }

  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

// --------------------------------------------------------------------------- //
// Pack PNGs into a multi-resolution .ico
// --------------------------------------------------------------------------- //
function packIco(images) {
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0) // reserved
  header.writeUInt16LE(1, 2) // type: 1 = icon
  header.writeUInt16LE(images.length, 4)

  let offset = 6 + 16 * images.length
  const entries = Buffer.alloc(16 * images.length)
  images.forEach((img, i) => {
    const e = 16 * i
    const dim = img.size >= 256 ? 0 : img.size // 0 means 256 in ICO
    entries.writeUInt8(dim, e + 0)
    entries.writeUInt8(dim, e + 1)
    entries.writeUInt8(0, e + 2) // palette
    entries.writeUInt8(0, e + 3) // reserved
    entries.writeUInt16LE(1, e + 4) // planes
    entries.writeUInt16LE(32, e + 6) // bpp
    entries.writeUInt32LE(img.data.length, e + 8)
    entries.writeUInt32LE(offset, e + 12)
    offset += img.data.length
  })

  return Buffer.concat([header, entries, ...images.map((i) => i.data)])
}

// --------------------------------------------------------------------------- //
// Main
// --------------------------------------------------------------------------- //
function main() {
  const pngBySize = new Map()
  for (const size of [...ICO_SIZES, APPLE_SIZE]) {
    const png = encodePng(size, size, rasterize(size))
    pngBySize.set(size, png)
    console.log(`  ${size}px -> ${png.length} bytes`)
  }

  const ico = packIco(ICO_SIZES.map((size) => ({ size, data: pngBySize.get(size) })))
  const icoPath = join(PUBLIC_DIR, 'favicon.ico')
  writeFileSync(icoPath, ico)
  console.log(`Wrote ${icoPath} (${ico.length} bytes)`)

  const applePath = join(PUBLIC_DIR, 'apple-touch-icon.png')
  writeFileSync(applePath, pngBySize.get(APPLE_SIZE))
  console.log(`Wrote ${applePath} (${pngBySize.get(APPLE_SIZE).length} bytes)`)
}

main()
