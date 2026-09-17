"use client";

/**
 * SearchAutocomplete — the graph search box, with a live result dropdown.
 *
 * The result list is the *same* filtered node list the page already derived
 * (`graph.nodes` matching the query, capped at 30) — this component does not
 * run its own search, so it cannot show a node the graph does not contain.
 *
 * Keyboard: ↑/↓ move the active row, Enter picks it (or falls through to the
 * caller's free-text submit, which the system namespace uses to search the
 * full compiled graph), Escape closes. Moving the active row calls `onActive`
 * so the caller can drive the graph's existing selection highlight; picking a
 * row clears the query.
 */
import { useEffect, useRef, useState } from "react";
import { Lucide } from "@/components/ui/LucideIcon";
import { colorOf, type KNode } from "@/lib/knowledge/types";

interface Props {
  query: string;
  onQueryChange: (q: string) => void;
  /** Real nodes matching the query, already filtered and capped by the page. */
  hits: KNode[];
  /** The node the graph currently has selected — drives `aria-selected`. */
  selectedId: string | null;
  /** Called as the active row changes so the graph highlights it. */
  onActive: (node: KNode) => void;
  /** Called on Enter / click: commit the choice. */
  onPick: (node: KNode) => void;
  /** Enter with no active row — the system graph's "search everything" path. */
  onSubmit?: () => void;
  placeholder: string;
  busy?: boolean;
  showSearchAll?: boolean;
}

export default function SearchAutocomplete({
  query,
  onQueryChange,
  hits,
  selectedId,
  onActive,
  onPick,
  onSubmit,
  placeholder,
  busy = false,
  showSearchAll = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const blurTimer = useRef<number | null>(null);
  /** Kept in a ref so the preview effect never re-fires on callback identity. */
  const active = useRef(onActive);
  active.current = onActive;

  const hasQuery = query.trim().length > 0;
  const visible = open && hasQuery && hits.length > 0;

  useEffect(() => {
    setCursor(0);
  }, [query]);

  // Preview the active row in the graph. The page turns this into the existing
  // selection state, which is the only highlight the canvas understands.
  useEffect(() => {
    if (!visible) return;
    const node = hits[Math.min(cursor, hits.length - 1)];
    if (node) active.current(node);
  }, [cursor, hits, visible]);

  useEffect(() => {
    if (!visible) return;
    const el = listRef.current?.children[cursor] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [cursor, visible]);

  useEffect(() => () => {
    if (blurTimer.current) window.clearTimeout(blurTimer.current);
  }, []);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setCursor((c) => (hits.length ? Math.min(c + 1, hits.length - 1) : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      const node = hits[Math.min(cursor, hits.length - 1)];
      if (visible && node) {
        e.preventDefault();
        onPick(node);
      } else {
        onSubmit?.();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      e.currentTarget.blur();
    }
  };

  return (
    <div className="ku-search ku-search--side">
      <Lucide name="search" size={13} aria-hidden="true" />
      <input
        id="ku-search"
        value={query}
        onChange={(e) => {
          onQueryChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          blurTimer.current = window.setTimeout(() => setOpen(false), 120);
        }}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        aria-label="Search the knowledge graph"
        role="combobox"
        aria-expanded={visible}
        aria-controls="ku-search-list"
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
      />
      {query && (
        <button
          type="button"
          className="ku-search__x"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            onQueryChange("");
            setOpen(false);
          }}
          aria-label="Clear search"
        >
          <Lucide name="x" size={12} />
        </button>
      )}
      {showSearchAll && (
        <button
          type="button"
          className="ku-search__go"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => onSubmit?.()}
          disabled={busy}
        >
          {busy ? "…" : "All"}
        </button>
      )}
      <kbd>⌘K</kbd>

      {visible && (
        <div
          id="ku-search-list"
          ref={listRef}
          className="ku-hits"
          role="listbox"
          aria-label="Search results"
        >
          {hits.map((n, i) => (
            <button
              key={n.id}
              type="button"
              role="option"
              aria-selected={n.id === selectedId}
              className={`ku-hits__opt${i === cursor ? " is-cursor" : ""}`}
              onMouseEnter={() => setCursor(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onPick(n)}
            >
              <span className="ku-hits__dot" style={{ background: colorOf(n.type) }} aria-hidden="true" />
              <span className="ku-hits__label">{n.label}</span>
              <span className="ku-hits__type">{n.type}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
