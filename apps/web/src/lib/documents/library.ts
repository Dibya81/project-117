"use client";

/**
 * Canonical document library.
 *
 * Until now the Documents page listed seven hand-written rows while the real
 * refinery corpus sat beside it, disconnected. This joins them into one list.
 *
 *   REGISTER ROWS    src/lib/mock/console.ts — the console's document records:
 *                    size, index status, timestamps, citation links.
 *   CORPUS DOCUMENTS public/knowledge/refinery-document.json, generated from
 *                    data/knowledge/** by scripts/build_document_field.py —
 *                    actual parsed content: headings, body lines, tables and
 *                    extracted entity tags. 18 source documents.
 *   KNOWLEDGE BASE   the same artifact's 23 dossier sections, grouped under
 *                    the master record.
 *
 * Some register rows and corpus documents are the *same document* —
 * `SOP-14.2.pdf` and `SOP-14.2_instrument_failure.md`. Those are matched on a
 * normalised filename stem and merged, so the row carries both its register
 * metadata and its parsed text. A record is enriched only when the corpus
 * genuinely holds that document; nothing is duplicated and nothing invented.
 */
import type { DocumentRecord } from "@/types";

export interface CorpusSection {
  slug: string;
  title: string;
  doc: string;
  source: string;
  kind: string;
  lines: string[];
  table?: string[][] | null;
  entities: string[];
  chars: number;
}

interface CorpusPayload {
  generated: string;
  source_dirs?: string[];
  count: number;
  skipped_steel?: number;
  master_sections?: CorpusSection[];
  sections: CorpusSection[];
}

export interface DocContent {
  title: string;
  lines: string[];
  table?: string[][];
  entities: string[];
  source: string;
  chars: number;
}

export interface LibraryDoc extends DocumentRecord {
  /** Real parsed content, present when the corpus holds this document. */
  content?: DocContent;
  /** Set on the master knowledge base record. */
  sectionCount?: number;
}

/** Per-section chunk files are named `NN-slug.md`; the dossier is the master. */
const SECTION_RE = /^\d+[a-z]?-/;
const MASTER_FILENAME = "REFINERY-TECHNICAL-KNOWLEDGE-BASE.md";
const MASTER_ID = "kb:refinery-technical-knowledge-base";

export interface LibraryStats {
  register: number;
  corpus: number;
  kbSections: number;
  enriched: number;
  total: number;
}

let cache: { docs: LibraryDoc[]; stats: LibraryStats } | null = null;
let inflight: Promise<{ docs: LibraryDoc[]; stats: LibraryStats }> | null = null;

function normStem(name: string): string {
  return name
    .replace(/\.[a-z0-9]+$/i, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function toContent(s: CorpusSection): DocContent {
  return {
    title: s.title,
    lines: s.lines ?? [],
    table: s.table ?? undefined,
    entities: s.entities ?? [],
    source: s.source,
    chars: s.chars,
  };
}

/** The corpus document that is the same document as `filename`, if any. */
function matchCorpus(filename: string, corpus: CorpusSection[]): CorpusSection | undefined {
  const want = normStem(filename);
  if (!want) return undefined;
  return (
    corpus.find((s) => normStem(s.doc) === want) ??
    corpus.find((s) => {
      const have = normStem(s.doc);
      return have.startsWith(want) || want.startsWith(have);
    })
  );
}

export async function loadLibrary(mock: DocumentRecord[]): Promise<{ docs: LibraryDoc[]; stats: LibraryStats }> {
  if (cache) return cache;
  if (inflight) return inflight;

  inflight = (async () => {
    let all: CorpusSection[] = [];
    let corpusCount = 0;
    try {
      const res = await fetch("/knowledge/refinery-document.json");
      if (res.ok) {
        const payload = (await res.json()) as CorpusPayload;
        all = payload.sections ?? [];
        corpusCount = payload.count ?? all.length;
      }
    } catch {
      // Offline corpus is a smaller library, not a broken page. The register
      // rows still render; nothing is faked to fill the gap.
      all = [];
    }

    const kbSections = all.filter((s) => SECTION_RE.test(s.doc));
    const corpus = all.filter((s) => !SECTION_RE.test(s.doc));

    const stamp = mock[0]?.updated_at ?? new Date().toISOString();
    const docs: LibraryDoc[] = [];
    let enriched = 0;

    // 1. Register rows, enriched where the corpus holds the same document.
    const consumed = new Set<string>();
    for (const m of mock) {
      const hit = matchCorpus(m.filename, corpus);
      if (hit) {
        consumed.add(hit.slug);
        enriched += 1;
        docs.push({
          ...m,
          content: toContent(hit),
          metadata: { ...m.metadata, source: hit.source, entities: hit.entities.length },
        });
      } else {
        docs.push({ ...m });
      }
    }

    // 2. Corpus documents that no register row describes.
    for (const s of corpus) {
      if (consumed.has(s.slug)) continue;
      docs.push({
        id: `kb:${s.slug}`,
        filename: s.doc,
        content_type: s.doc.endsWith(".json") ? "application/json" : "text/markdown",
        size_bytes: s.chars,
        status: "indexed",
        metadata: { source: s.source, entities: s.entities.length },
        created_at: stamp,
        updated_at: stamp,
        content: toContent(s),
      });
    }

    // 3. The knowledge base master record, carrying its section index.
    if (kbSections.length) {
      docs.unshift({
        id: MASTER_ID,
        filename: MASTER_FILENAME,
        content_type: "text/markdown",
        size_bytes: kbSections.reduce((n, s) => n + s.chars, 0),
        status: "indexed",
        metadata: {
          sections: kbSections.length,
          entities: kbSections.reduce((n, s) => n + s.entities.length, 0),
          kind: "knowledge-base",
        },
        created_at: stamp,
        updated_at: stamp,
        sectionCount: kbSections.length,
        content: {
          title: "Refinery technical knowledge base — 5-year operating dossier",
          lines: kbSections.map((s) => s.title),
          entities: [...new Set(kbSections.flatMap((s) => s.entities))].slice(0, 40),
          source: "data/knowledge/REFINERY-TECHNICAL-KNOWLEDGE-BASE.md",
          chars: kbSections.reduce((n, s) => n + s.chars, 0),
        },
      });

      // 3b. And each section as its own citable row.
      for (const s of kbSections) {
        docs.push({
          id: `kb:${s.slug}`,
          filename: s.doc,
          content_type: "text/markdown",
          size_bytes: s.chars,
          status: "indexed",
          metadata: { section: s.title, source: s.source, entities: s.entities.length },
          created_at: stamp,
          updated_at: stamp,
          content: toContent(s),
        });
      }
    }

    const stats: LibraryStats = {
      register: mock.length,
      corpus: corpusCount,
      kbSections: kbSections.length,
      enriched,
      total: docs.length,
    };
    cache = { docs, stats };
    return cache;
  })();

  return inflight;
}

export function clearLibraryCache() {
  cache = null;
  inflight = null;
}
