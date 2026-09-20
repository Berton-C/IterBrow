# NodeQuest Chapter 1 — Real-Game Design Draft (pre-Godot, for user review)
Date: 2026-09-17 19:56. Status: DRAFT, not built. Godot not yet installed (awaiting user "go").

## User's vision (verbatim pivot, 19:50)
Actual playable game. Environment progresses because player GAINS and APPLIES knowledge.
Text woven into gameplay — NOT read-then-answer layout. Godot builds the game environment.

## Chapter 1 content backbone (from nodes.json / OpenStax Physics Ch 1)
- 1.1 What is physics: definitions, scope (atoms -> galaxies)
- 1.2 Scientific methods: hypothesis -> experiment -> theory -> law
- 1.3 Language of physics: SI units, measurement, unit conversion

## Core mechanic ("Knowledge IS the key")
Player explores a 2D world. Obstacles are NOT combat — they are phenomena.
The only tool that opens paths is applying a physics idea. Wrong applications
never punish; the world gently reacts ("the gate hums, unconvinced") and hints.

## World sketch (blend proposal — scales + lab feel)
Room 1 — The Human Room (scale: everyday). A character, "The Questioner",
asks WHY the lamp glows. Player gathers observations -> forms hypothesis
(applied 1.2: pick a claim, design a test). Correct test = lamp world lights up,
door opens. Text = in-world dialogue/signs, never a worksheet.
Room 2 — The Unit Gate. A bridge whose planks demand units: signs say "3",
"30", "300" — player must attach the right SI unit (km? m? s? kg?) to each
plank to cross. Wrong = plank wobbles, funny rebalance animation, retry freely.
Room 3 — The Zoom Portal (applied 1.1): telescope + microscope stations;
player chooses where a given phenomenon lives (galaxy / human / atom scale).
Choosing correctly zooms the camera THERE — the world literally becomes
that scale. Chapter ends: portal to Ch 2 opens, tier sparkle gains recorded.

## Persistence & win/win rules (carry over from Phase 1)
Sparkles for right AND generous-wrong; tiers only shine brighter (— ->
Sparkling -> Radiant -> Dazzling); save via localStorage (HTML5 export) mirroring
nodequest.save.v1 conventions so the browser prototype and game share progress.

## Build plan once Godot is downloaded
1. Godot 4.5 macOS universal (verified link) -> new project, 2D.
2. Three rooms as scenes; dialogue via built-in Dialogic-free simple
   Label/typewriter (no addon deps for slice 1).
3. HTML5 export -> host in iter/nodequest/godot/export/ -> open in IterBrow tab.
4. Machine-verify: DOM/canvas load, simulated keypresses, save roundtrip.

## Open questions for user (sent 19:55)
feel (adventure vs puzzle-lab vs blend) / look (pixel vs geometric vs
atmospheric) / download OK.
