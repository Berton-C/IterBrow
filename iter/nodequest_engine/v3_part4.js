// tap overrides + quiz + round progression
function tapCargo(i){sel=i;vee("Riddle for cargo ???  "+RIDDLES[CARGO[i].k][V3.round]+"  (Tap a dock when you've deduced its role.)");sfx("pick");}
function tapDock(i){
 if(sel<0||!cargoLeft.includes(sel)){vee(v3ClueText());return}
 if(dockOrder[i]===CARGO[sel].k){ // correct
  cargoLeft=cargoLeft.filter(x=>x!==sel);sel=-1;sfx("ship");
  if(cargoLeft.length===0){nextRound();return}
  vee("Correct ship! Now the next cargo... "+v3ClueText());
 }else{sfx("wrong");clownFx(V3_CLOWN[i]);vee("CLANG! Wrong dock - the vesicle is lost in the cytosol! Re-deduce from the riddles and glyph keys.");}
 drawDocks();drawCargo();meter();}
function v3Checkpoint(q){V3.quiz=q;
 if(!V3.quizBox){V3.quizBox=document.createElement("div");V3.quizBox.style.cssText="position:absolute;left:50%;top:60px;transform:translateX(-50%);max-width:600px;background:#0d1f1a;border:2px solid #c8a468;border-radius:12px;padding:14px;z-index:50;color:#cfe3d8;font-family:sans-serif";
  document.body.appendChild(V3.quizBox);}
 V3.quizBox.style.display="block";
 V3.quizBox.innerHTML="<div style='color:#c8a468;font-weight:bold;margin-bottom:8px'>CHECKPOINT "+(V3.round+1)+" - Vee tests your reasoning</div><div style='margin-bottom:10px'>"+q[0]+"</div>"+q[1].map((a,j)=>"<button style='display:block;margin:4px 0;padding:8px 14px;background:#1d3a33;color:#cfe3d8;border:1px solid #5d7a6e;border-radius:8px;cursor:pointer' onclick='quizAns("+j+")'>"+a+"</button>").join("");
 (window.__veeQ=q);}
function quizAns(j){const q=window.__veeQ;if(!q)return;
 if(j===q[2]){V3.quizBox.innerHTML="<div style='color:#8fe39a'>+ "+q[3]+"</div>";sfx("ship");setTimeout(()=>{V3.quizBox.style.display="none";V3.roundStart();},1800);}
 else{sfx("wrong");V3.quizBox.querySelector("button:nth-child("+(j+1)+")")&&(V3.quizBox.querySelector("button:nth-child("+(j+1)+")").style.textDecoration="line-through");vee("Not quite - reread the glyph clues and try again.");}}
function nextRound(){
 if(V3.round>=2){ // finished all 3 rounds
  vee("ALL THREE ROUNDS COMPLETE - the vesicle system is mastered! Shipment meter full. Chapter beaten with pure deduction.");
  sfx("ship");window.__v3done=true;drawDocks();drawCargo();meter();return}
 v3Checkpoint(CHECKPOINTS[V3.round]);}
V3.roundStart=function(){
 V3.round++;v3Init();cargoLeft=[0,1,2];sel=-1;
 drawDocks();drawCargo();vee(v3ClueText());meter();};
// boot v3 (replace V2 init): shuffle dock roles, hide labels
v3Init();cargoLeft=[0,1,2];sel=-1;drawDocks();drawCargo();vee(v3ClueText());meter();
