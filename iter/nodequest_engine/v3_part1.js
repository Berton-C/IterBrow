// ==== V3 PUZZLE LAYER (2026-09-18): Stage A riddle-cargo, Stage B glyph-key port lock, Stage C 3-round gauntlet ====
const V3={round:0,glyphs:[],anchor:"",quiz:null,quizBox:null};
const RIDDLES={
 insulin:["I speak for the whole body, yet I die at the waste gate.","I am the courier of commands - never ride out with the trash.","The body will not hear the cell without me."],
 waste:["I am what the cell must be rid of - find my gate before I sour the story.","My port leads OUT and never back.","Untouched, I poison the whole cell's mood."],
 lipid:["I am the fresh brick the membrane grows from - never a message, never trash.","Growth is my cargo - the wall grows where I arrive.","I do not speak to the body; I become part of its wall."]};
const GLYPHS={a:{icon:"\u2B21",name:"alpha key"},b:{icon:"\u2B20",name:"beta key"},c:{icon:"\u2B22",name:"gamma key"},d:{icon:"\u2B23",name:"delta key"},e:{icon:"\u2B24",name:"epsilon key"},f:{icon:"\u2B25",name:"zeta key"}};
const CHECKPOINTS=[
 ["Why could the waste gate be ruled out for the hormone cargo?",
  ["Because the waste port is the only one without a shared key","Because the riddle said the hormone dies at the waste gate","Because hormone cargo is pink and waste is brown"],1,
  "Exactly - the riddle gave a DIRECT exclusion clue. Riddles can rule ports out, not just name them."],
 ["Two docks share exactly one key, and one dock shares none. What does the lone dock tell you?",
  ["It is the odd one out - it takes the trash","Nothing - keys are just decoration","It must be the hormone gate"],0,
  "Right - the two sister ports (message + brick) are the ones sharing a key; the lone port serves the trash by elimination."],
 ["The vesicle drifted to the wrong dock. Which reasoning would have saved you?",
  ["Cargo colors","Cargo shapes","Riddle exclusion clues + glyph deduction"],2,
  "Yes - the DEDUCED identity (riddle + glyph logic) is what proves which dock is which before you ship."]];
