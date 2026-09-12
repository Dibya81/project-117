/**
 * Document field content — the real corpus, read from the backend.
 *
 * This module used to hold `CORPUS_PAGES`: twenty-odd hand-written pages
 * attributed to `data/knowledge/*.md` and `data/demo/**`, both of which have
 * been deleted, plus a loader for `public/knowledge/refinery-document.json`,
 * an artifact generated from those same deleted sources. The Documents page
 * therefore animated pages for documents the plant does not have — IR-204
 * compressor inspections, C-3 vibration baselines — while the actual corpus sat
 * in the vector index, unread.
 *
 * It now reads `GET /api/documents/{id}/chunks`. After parsing, that table is
 * the only place a document's text exists, so the field shows what was really
 * indexed.
 *
 * Honest limitation: `entities` is always empty. Nothing in the pipeline does
 * named-entity extraction, and the scan pass that lit up tags on each page read
 * them from the hand-written pages. An empty list means the scan has nothing to
 * reveal, rather than revealing something invented.
 */
import { api } from "@/lib/api";

export type PageKind = "procedure" | "inspection" | "baseline" | "manual" | "record" | "register";

export const KIND_LABEL: Record<PageKind, string> = {
  procedure: "Procedure",
  inspection: "Inspection",
  baseline: "Baseline",
  manual: "Manual",
  record: "Record",
  register: "Register",
};

export interface DocPage {
  id: string;
  /** The library document this page belongs to. */
  doc: string;
  /** The real library id, so selecting a page opens the real record. */
  documentId: string;
  section: string;
  kind: PageKind;
  /** Body lines, rendered as text on the page when it is large enough. */
  lines: string[];
  /** Optional table: first row is the header. */
  table?: string[][];
  /** Empty until entity extraction exists. Never fabricated. */
  entities: string[];
  page?: number;
}

/**
 * Classify a document by its filename. The corpus is small and its naming is
 * consistent (SOP_, IR_, Work_Order_, Safety_Incident_…), so this is a
 * presentation hint about the record, not a claim about its contents.
 */
export function kindOf(filename: string): PageKind {
  const f = filename.toLowerCase();
  if (f.includes("sop") || f.includes("procedure")) return "procedure";
  if (f.includes("inspection") || f.startsWith("ir-")) return "inspection";
  if (f.includes("baseline") || f.includes("vibration")) return "baseline";
  if (f.includes("manual")) return "manual";
  if (f.includes("work_order") || f.includes("incident") || f.includes("report")) return "record";
  return "register";
}

/** How many library documents to draw pages from, and pages per document. */
const DOCUMENTS = 8;
const CHUNKS_PER_DOC = 3;

/** A markdown pipe table becomes a real table; anything else stays text. */
function splitTable(text: string): { lines: string[]; table?: string[][] } {
  const rows = text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("|") && l.endsWith("|"))
    .map((l) =>
      l
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim()),
    )
    // Drop markdown separator rows ("|---|---|").
    .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c)));
  if (rows.length > 1 && rows[0].length > 1) {
    return { lines: [], table: rows.map((r) => r.slice(0, 6)) };
  }
  return { lines: text.split("\n").map((l) => l.trim()).filter(Boolean).slice(0, 9) };
}

/**
 * Load pages from the live corpus. A document that cannot be read contributes
 * nothing; the field then shows fewer pages rather than inventing any.
 */
export async function loadCorpusPages(): Promise<DocPage[]> {
  const library = await api.documents.list();
  const indexed = library.documents.filter((d) => d.status === "indexed").slice(0, DOCUMENTS);

  const perDocument = await Promise.all(
    indexed.map(async (doc) => {
      try {
        const { chunks } = await api.documents.chunks(doc.id, CHUNKS_PER_DOC);
        return chunks.map<DocPage>((c) => {
          const section = c.heading_path?.[c.heading_path.length - 1];
          const { lines, table } = splitTable(c.text ?? "");
          return {
            id: c.chunk_id,
            doc: doc.filename,
            documentId: doc.id,
            section: section || `${c.block_type || "paragraph"} · chunk ${c.chunk_index}`,
            kind: kindOf(doc.filename),
            lines,
            ...(table ? { table } : {}),
            entities: [],
            ...(c.page != null ? { page: c.page } : {}),
          };
        });
      } catch {
        return [];
      }
    }),
  );

  return perDocument.flat();
}
