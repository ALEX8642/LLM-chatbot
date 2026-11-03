import { useState } from 'react'
import { pageUrl } from './api'
import { boxStyle, type Box } from './boxes'

interface Props {
  manual: string
  page: number | null
  boxes: Box[]
}

/** The page render with the claim's boxes drawn over it, once that page has loaded. */
export default function PageViewer({ manual, page, boxes }: Props) {
  const [loaded, setLoaded] = useState<string | null>(null)
  if (page == null) return <p className="p-6 text-slate-500">Select a claim to see its source on the page.</p>
  const src = pageUrl(manual, page)
  return (
    <figure className="m-0">
      <figcaption className="mb-1 text-sm text-slate-500">Page {page}</figcaption>
      <div className="relative inline-block w-full">
        <img
          key={src}
          src={src}
          alt={`page ${page}`}
          onLoad={() => setLoaded(src)}
          className="block w-full shadow"
        />
        {loaded === src &&
          boxes.map((b, i) => (
            <div
              key={i}
              data-testid="box"
              style={boxStyle(b)}
              className="pointer-events-none absolute rounded-sm bg-amber-300/30 ring-2 ring-amber-500"
            />
          ))}
      </div>
    </figure>
  )
}
