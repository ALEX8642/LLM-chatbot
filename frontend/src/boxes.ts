import type { CSSProperties } from 'react'

/** A page-normalised box (0..1 of page width and height), as stored at ingestion. */
export interface Box {
  x0: number
  y0: number
  x1: number
  y1: number
}

const pct = (v: number) => `${+(v * 100).toFixed(4)}%`

/** Box → CSS position over the page render; the render keeps the page's aspect ratio. */
export function boxStyle(box: Box): CSSProperties {
  return { left: pct(box.x0), top: pct(box.y0), width: pct(box.x1 - box.x0), height: pct(box.y1 - box.y0) }
}
