# Vendored ThreeUI authored sources

These files are the **exact authored sources** published by ThreeUI for the three
components Project 117 uses. They are copied byte-for-byte and every SHA-256 was
verified after download (`node .p117-audit/vendor-threeui.mjs` at the repo root).

| File | SHA-256 | Source |
| --- | --- | --- |
| `character-carousel/CharacterCarousel.tsx` | `3bc9c80e8201be3cde79697e8cddba6f4f8b1a3c4a5fb7ce7533dd6479409472` | [character-filmstrip.json](https://threeui.com/source-code/character-filmstrip.json) |
| `character-carousel/sources/character-filmstrip.html` | `4c98939e0e2b67efabcb8561c8b2e53b8c756e97bda44906b235ee7bc8f68b1c` | [character-filmstrip.json](https://threeui.com/source-code/character-filmstrip.json) |
| `animated-top-dock/AnimatedTopDock.tsx` | `50ddbba7ebc81565f42bd14dda34efb45e7b18c1aa47e97f196256ffedb4478f` | [animated-top-dock.json](https://threeui.com/source-code/animated-top-dock.json) |
| `animated-top-dock/topDockController.ts` | `506ab23d4d42cf1b5bc89131e7714586ee107381bb18d9b0302766e9a1dee2bd` | animated-top-dock.json |
| `animated-top-dock/retroPixelField.ts` | `54f0469be51dfce2da7ce37c952d42c583cc7996794bf96d1ea0b2bb35d94115` | animated-top-dock.json |
| `animated-top-dock/glassParticleField.ts` | `bc9f07ae6da33b28f82303ea937095806f8e3a2ab08bd1301ae8457aaf0c3464` | animated-top-dock.json |
| `threeui.css` | `efe4447139f1358dd8e9be68edf6fa46cbefbd1de423a4d6c439ca61d2c8eccf` | all three manifests |
| `fonts/fragment-mono.woff2` | `4f4dc27f4a770c0d02fde800daa836c8adc0d1e423b28da74baaf0d1cc3ab96c` | [MengTo/threeui](https://github.com/MengTo/threeui/blob/main/src/shaders/fonts/fragment-mono.woff2) |

## Why these are reference copies, not the runtime import

The authored `.tsx` files are written for ThreeUI's own Vite build. They import
`./sources/<name>.html?raw` (a Vite loader) and alias `three128`, and they pull in
~40 sibling HTML sources that are outside this project's required-file set.
Copying them alone cannot compile under Next's webpack pipeline.

Project 117 therefore **runs** the identical authored implementation through the
published package `@designcodeio/threeui@1.2.0`, whose `lib-dist` build is the
same source with the `?raw` imports already resolved. These files exist so the
exact source is auditable in-repo and hash-verifiable.

`src/shaders` is excluded from `tsconfig.json` for that reason. Nothing in the
app imports from this directory. Do not edit these files — it breaks the hashes.
