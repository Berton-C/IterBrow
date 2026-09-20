function v3ClueText(){const g=i=>V3.glyphs[i].map(x=>GLYPHS[x].icon).join(" ");
 return "ROUND "+(V3.round+1)+"/3 - Dock glyphs: A "+g(0)+" | B "+g(1)+" | C "+g(2)+". Vee whispers: the two SISTER ports share one key - they serve the message and the brick; the brick gate also wears the lone "+GLYPHS[V3.anchor].icon+" key; the port sharing NO key takes only the trash.";}
function v3Init(){
 const keys=Object.keys(GLYPHS).sort(()=>Math.random()-.5),p=keys.slice(0,5);
 dockOrder=[0,1,2].sort(()=>Math.random()-.5);
 // Solvable template: sisters share p0; brick sister also wears anchor p1; lone dock p3+p4
 V3.anchor=p[1];
 const sisters=[{g:[p[0],p[1]],brick:true},{g:[p[0],p[2]],brick:false}];
 sisters.sort(()=>Math.random()-.5); // random which sister position is brick
 // dockGlyphs built in DOCK POSITION order: role of dock i is CARGO[dockOrder[i]]
 // roles: 0=hormone,1=waste,2=lipid(brick)
 const posOf=k=>dockOrder.indexOf(k); // dock position serving cargo k
 V3.glyphs=[[],[],[]];
 V3.glyphs[posOf(2)]=sisters[0].g; // brick dock (lipid) wears anchor
 V3.glyphs[posOf(0)]=sisters[1].g; // hormone dock shares p0 but NOT anchor
 V3.glyphs[posOf(1)]=[p[3],p[4]];  // waste dock: lone, no shared key
}
