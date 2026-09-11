"use client";

/** Chapter rail (01–07) on the right edge; scrolls the track to a scene. */

export interface Chapter {
  id: string;
  label: string;
  progress: number; // track position the chapter starts at
}

export default function ChapterNavigation({
  chapters,
  current,
  onSelect,
}: {
  chapters: Chapter[];
  current: number;
  onSelect: (progress: number) => void;
}) {
  return (
    <nav className="p117-chapters" aria-label="Story chapters">
      {chapters.map((chapter, i) => (
        <button
          key={chapter.id}
          type="button"
          aria-current={i === current}
          aria-label={`Chapter ${chapter.id}: ${chapter.label}`}
          onClick={() => onSelect(chapter.progress)}
        >
          {chapter.id}
          <span>{chapter.label}</span>
        </button>
      ))}
    </nav>
  );
}
