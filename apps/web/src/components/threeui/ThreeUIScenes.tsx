"use client";

import { AnimatedTopDock } from "@designcodeio/threeui/components/AnimatedTopDock";
import { CharacterCarousel } from "@designcodeio/threeui/components/CharacterCarousel";
import { StructureFlowCollection } from "@designcodeio/threeui/components/StructureFlowCollection";
import "@designcodeio/threeui/style.css";

export function ConsoleCommandDock() {
  return (
    <div className="cs-threeui-dock" aria-hidden="true">
      <AnimatedTopDock
        variant="modern"
        proximity={122}
        spring={0.19}
        damping={0.7}
        widthGrowth={17}
        heightGrowth={16}
        drop={3.5}
      />
    </div>
  );
}

export function LogicCoreScene() {
  return (
    <div className="cs-threeui-frame cs-threeui-frame--logic">
      {/* The authored component ships its own light mode. The console now runs a
          bright canvas, and the default dark register rendered as a pure-black
          block on white — 7% of the home page in `#000000`. `mode="light"` is
          the component's own variant, so the source stays untouched. */}
      <StructureFlowCollection
        variant="logic-core"
        mode="light"
        hue={0}
        saturation={1}
        brightness={1}
      />
    </div>
  );
}

export function KnowledgeFilmstripScene() {
  return (
    <div className="cs-threeui-frame cs-threeui-frame--filmstrip">
      <CharacterCarousel
        variant="filmstrip"
        speed={1}
        scale={1}
        opacity={1}
        hue={0}
        saturation={1}
        brightness={1}
      />
    </div>
  );
}
