"use client";

/**
 * Typewriter — streams text character-by-character with a caret.
 * Used for AI answers in the workspace; ~90 chars/sec with jitter.
 */
import { useEffect, useRef, useState } from "react";

export function Typewriter({
  text,
  speed = 26,
  onDone,
  className,
}: {
  text: string;
  speed?: number;
  onDone?: () => void;
  className?: string;
}) {
  const [len, setLen] = useState(0);
  const doneRef = useRef(false);

  useEffect(() => {
    doneRef.current = false;
    setLen(0);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setLen(text.length);
      return;
    }
    let i = 0;
    let timer: ReturnType<typeof setTimeout>;
    const step = () => {
      // burst 2-4 chars per tick for a natural stream
      i = Math.min(text.length, i + 2 + Math.floor(Math.random() * 3));
      setLen(i);
      if (i < text.length) {
        timer = setTimeout(step, speed + Math.random() * 22);
      } else if (!doneRef.current) {
        doneRef.current = true;
        onDone?.();
      }
    };
    timer = setTimeout(step, 240);
    return () => clearTimeout(timer);
  }, [text, speed, onDone]);

  const done = len >= text.length;

  return (
    <span className={className}>
      {text.slice(0, len)}
      {!done && <span className="fx-caret" aria-hidden="true">▌</span>}
      <style jsx>{`
        .fx-caret {
          color: var(--cyan);
          animation: p117-blink 0.9s steps(1) infinite;
          margin-left: 1px;
        }
      `}</style>
    </span>
  );
}
