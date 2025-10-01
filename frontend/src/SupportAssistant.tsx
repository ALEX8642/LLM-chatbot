import React, { useMemo, useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// Layer styles for selectable text & annotations
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "pdfjs-dist/web/pdf_viewer.css";

// Bundle the PDF.js v5 worker locally (no CDN, no CORS/version issues)
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;

/* ---------------------------------------------
   BACKEND
---------------------------------------------- */

type Manual = { id: string; label: string; pdf_url: string };

import { config } from './config';

const BACKEND_ASK_URL = `${config.BACKEND_BASE}/ask`;

/* ---------------------------------------------
   TYPES (aligns with Python payload)
---------------------------------------------- */

type Citation = { page: number; product?: string | null; score?: number | null };
type Section = {
  page: number;
  product?: string | null;
  score?: number | null;
  snippet?: string;
  full?: string;
};
type AskResponse = {
  answer: string;
  citations: Citation[];
  manual_sections: Section[];
  used_model: string;
  top_pages: number[];
  manual_id?: string;
};

/* ---------------------------------------------
   COMPONENT
---------------------------------------------- */

export default function SupportAssistant() {
  // Manuals + manual selection
  const [manuals, setManuals] = useState<Manual[]>([]);
  const [manualId, setManualId] = useState<string>("");

  useEffect(() => {
    fetch(`${config.BACKEND_BASE}/manuals`)
      .then((r) => r.json())
      .then(setManuals)
      .catch((err) => console.error("Failed to load manuals:", err));
  }, []);

  useEffect(() => {
    if (manuals.length && !manualId) {
      setManualId(manuals[0].id);
    }
  }, [manuals]);

  const pdfUrl = useMemo(
    () => manuals.find((m) => m.id === manualId)?.pdf_url ?? "",
    [manuals, manualId]
  );

  // PDF viewer
  const [numPages, setNumPages] = useState<number>();
  const [pageNumber, setPageNumber] = useState<number>(1);

  // Q&A
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(false);
  const [askError, setAskError] = useState<string>("");

  const fileSpec = useMemo(() => pdfUrl, [pdfUrl]);

  function onDocLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
  }

  async function handleAsk() {
    setAskError("");
    setLoading(true);
    setAnswer("");
    setCitations([]);
    setSections([]);

    try {
      const res = await fetch(BACKEND_ASK_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          manual_id: manualId,
          query,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Backend error (${res.status}): ${text}`);
      }

      const data: AskResponse = await res.json();
      setAnswer(data.answer || "");
      setCitations(data.citations || []);
      setSections(data.manual_sections || []);

      const jump =
        (Array.isArray(data.top_pages) && data.top_pages[0]) ||
        (data.citations && data.citations[0]?.page) ||
        1;
      setPageNumber(Math.max(1, Number(jump) || 1));

      if (data.manual_id) {
        setManualId(data.manual_id);
      }
    } catch (err: any) {
      console.error("ASK ERROR:", err);
      setAskError(err?.message || "Failed to fetch answer.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar (independent scroll) */}
      <aside className="w-80 min-w-72 border-r bg-white p-6 shadow-sm overflow-y-auto">
        <h1 className="text-xl font-bold mb-4">Support Assistant</h1>

        <label className="block text-sm font-medium mb-1">Manual</label>
        <select
          value={manualId}
          onChange={(e) => {
            setManualId(e.target.value);
            setPageNumber(1);
          }}
          className="w-full p-2 border rounded mb-4"
        >
          {manuals.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>

        <label className="block text-sm font-medium mb-1">Your question</label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask your question…"
          className="w-full p-3 border rounded-lg focus:ring focus:ring-blue-400 min-h-[120px]"
        />

        <button
          onClick={handleAsk}
          disabled={!query.trim() || !pdfUrl || loading}
          className="mt-3 w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>

        {askError && (
          <div className="mt-3 text-sm text-red-600">{askError}</div>
        )}

        {/* Citations */}
        {citations?.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-semibold mb-2">Cited pages</h3>
            <ul className="space-y-1">
              {citations.map((c, idx) => (
                <li key={`${c.page}-${idx}`}>
                  <button
                    onClick={() => setPageNumber(Math.max(1, c.page || 1))}
                    className="text-blue-600 hover:underline"
                    title={`Jump to page ${c.page}`}
                  >
                    Page {c.page}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>

      {/* Main content: fixed-height two-column grid */}
      <main className="flex-1 h-screen overflow-hidden">
        <div className="grid grid-cols-2 h-full">
          {/* Left column (independent scroll) */}
          <div className="min-w-0 h-full overflow-y-auto border-r">
            <section className="p-5 border-b bg-white">
              <h2 className="text-lg font-semibold mb-2">Answer</h2>
              {answer ? (
                <p className="whitespace-pre-line text-gray-800">{answer}</p>
              ) : (
                <p className="text-gray-500">
                  Ask a question to see the answer and citations here.
                </p>
              )}
            </section>

            {sections?.length > 0 && (
              <section className="p-5 border-b bg-white">
                <h3 className="text-sm font-semibold mb-3">Key manual sections</h3>
                <div className="space-y-3">
                  {sections.slice(0, 4).map((s, i) => (
                    <div
                      key={`${s.page}-${i}`}
                      className="border rounded p-3 bg-gray-50"
                    >
                      <button
                        className="text-blue-600 hover:underline"
                        onClick={() => setPageNumber(Math.max(1, s.page || 1))}
                        title={`Jump to page ${s.page}`}
                      >
                        Page {s.page}
                      </button>
                      {s.snippet && (
                        <p className="mt-2 text-sm text-gray-700">{s.snippet}</p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>

          {/* Right column: PDF (independent scroll) */}
          <div className="min-w-0 h-full overflow-y-auto bg-gray-100 p-5">
            {!pdfUrl ? (
              <div className="text-gray-500">Select a manual to load its PDF.</div>
            ) : (
              <div className="mx-auto max-w-3xl">
                <Document
                  file={fileSpec}
                  onLoadSuccess={onDocLoadSuccess}
                  onLoadError={(err) => console.error("onLoadError:", err)}
                  onSourceError={(err) => console.error("onSourceError:", err)}
                  loading={<div className="text-gray-600">Loading PDF…</div>}
                  error={<div className="text-red-600">Failed to load PDF.</div>}
                >
                  <Page pageNumber={pageNumber} />
                </Document>

                <div className="mt-4 flex items-center gap-3">
                  <button
                    onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
                    disabled={pageNumber <= 1}
                    className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <div className="text-gray-700">
                    Page {pageNumber} of {numPages ?? "—"}
                  </div>
                  <button
                    onClick={() =>
                      setPageNumber((p) => Math.min(numPages || p, p + 1))
                    }
                    disabled={!numPages || pageNumber >= (numPages || 1)}
                    className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
