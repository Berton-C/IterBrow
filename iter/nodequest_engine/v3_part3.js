// Puzzle-mode renderers + overrides (function declarations win over V2 via hoisting)
function drawDocks(){const D=document.getElementById("docks");D.innerHTML="";
 dockPts.forEach((p,i)=>{
  el("rect",{x:p.x-40,y:p.y-30,width:80,height:60,rx:12,fill:"rgba(13,31,26,.85)",stroke:"#5d7a6e","stroke-width":3,id:"dock"+i,cursor:"pointer"},D).addEventListener("pointerdown",()=>tapDock(i));
  const tt=el("title",{},D.lastChild);tt.textContent="port glyphs: "+V3.glyphs[i].map(x=>GLYPHS[x].name).join(" + ");
  el("text",{x:p.x,y:p.y-2,"text-anchor":"middle",fill:"#c8a468","font-size":20},D).textContent=V3.glyphs[i].map(x=>GLYPHS[x].icon).join(" ");
  el("text",{x:p.x,y:p.y+22,"text-anchor":"middle",fill:"#9fb8ac","font-size":12},D).textContent=["dock A","dock B","dock C"][i];});}
function drawCargo(){const G=document.getElementById("cargoG");G.innerHTML="";
 CARGO.forEach((t,i)=>{const x=190,y=250+i*150;
  if(!cargoLeft.includes(i)){el("rect",{x:x-60,y:y-34,width:120,height:68,rx:10,fill:"rgba(13,31,26,.5)",stroke:"#1d3a33"},G);
   el("text",{x:x,y:y+5,"text-anchor":"middle",fill:"#5d7a6e","font-size":13},G).textContent="??? - shipped";return}
  const gg=el("g",{transform:"translate("+x+" "+y+")",cursor:"pointer"},G);gg.dataset.i=i;
  el("path",{d:t.shape,fill:"rgba(13,31,26,.9)",stroke:t.col,"stroke-width":3},gg);
  el("circle",{r:4,fill:t.col,opacity:.9},gg);
  const tt=el("title",{},gg);tt.textContent="Riddle: "+RIDDLES[t.k][V3.round];
  el("text",{y:42,"text-anchor":"middle",fill:"#c8a468","font-size":14},gg).textContent="???";
  gg.addEventListener("pointerdown",ev=>{ev.preventDefault();tapCargo(i);});});}
