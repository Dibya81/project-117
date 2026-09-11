"use client";

/** Bottom hairline progress bar; driven imperatively via ref from the
 * parent's rAF loop so it never triggers a React re-render per frame. */
import { forwardRef, useImperativeHandle, useRef } from "react";
import type { RefObject } from "react";

export interface ScrollProgressHandle {
  set: (progress: number) => void;
}

const ScrollProgress = forwardRef<ScrollProgressHandle>(function ScrollProgress(_props, ref) {
  const barRef = useRef<HTMLElement>(null);

  useImperativeHandle(ref, () => ({
    set: (progress: number) => {
      barRef.current?.style.setProperty("transform", `scaleX(${progress})`);
    },
  }));

  return (
    <div className="p117-progress" aria-hidden="true">
      <i ref={barRef as RefObject<HTMLElement>} data-progress />
    </div>
  );
});

export default ScrollProgress;
