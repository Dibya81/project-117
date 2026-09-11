"use client";

/** Drawer + Modal — shared overlay primitives with escape/backdrop close. */
import { useEffect, type ReactNode } from "react";
import { Icon } from "./Icon";

function useEscape(onClose: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
}

export function Drawer({
  title,
  wide,
  onClose,
  children,
}: {
  title: string;
  wide?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEscape(onClose);
  return (
    <>
      <div className="cs-drawer__backdrop" onClick={onClose} aria-hidden="true" />
      <aside className={`cs-drawer${wide ? " cs-drawer--wide" : ""}`} role="dialog" aria-label={title}>
        <header className="cs-drawer__head">
          <strong style={{ fontSize: 14 }}>{title}</strong>
          <button className="cs-iconbtn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </header>
        <div className="cs-drawer__body">{children}</div>
      </aside>
    </>
  );
}

export function Modal({
  title,
  wide,
  onClose,
  children,
}: {
  title: string;
  wide?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEscape(onClose);
  return (
    <div className="cs-modal__backdrop" onClick={onClose}>
      <div
        className={`cs-modal${wide ? " cs-modal--wide" : ""}`}
        role="dialog"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="cs-drawer__head">
          <strong style={{ fontSize: 14 }}>{title}</strong>
          <button className="cs-iconbtn" style={{ marginLeft: "auto" }} onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </header>
        <div style={{ padding: 18 }}>{children}</div>
      </div>
    </div>
  );
}
