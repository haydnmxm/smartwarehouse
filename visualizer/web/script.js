/* Warehouse visualiser — readability tuned */
let frames=[],layout=[],zoneMap={};
let current=0,playing=false,timer=null,fps=2;
const $=id=>document.getElementById(id);

/* ---------- load ---------- */
function load(){
  fetch('run_dump.json.gz').then(r=>r.arrayBuffer()).then(buf=>{
    const text=new TextDecoder().decode(pako.inflate(new Uint8Array(buf)));
    const data=JSON.parse(text);
    layout=data.layout.zones??data.layout;
    frames=data.frames;
    layout.forEach(z=>zoneMap[z.id]=z);
    $('time-slider').max=frames.length-1;
    initFpsSelect();
    resizeCanvas(); drawFrame(0);
  });
}

/* ---------- init ---------- */
document.addEventListener('DOMContentLoaded',()=>{
  load();
  $('play').addEventListener('click',togglePlay);
  $('prev').addEventListener('click',()=>step(-1));
  $('next').addEventListener('click',()=>step(1));
  $('time-slider').addEventListener('input',e=>{
    current=+e.target.value; drawFrame(current);
  });
  $('fps').addEventListener('change',e=>{
    fps=+e.target.value; if(playing) startTimer();
  });
  window.addEventListener('resize',()=>{resizeCanvas(); drawFrame(current);});
});
function initFpsSelect(){
  const sel=$('fps');
  for(let i=1;i<=10;i++){
    const o=document.createElement('option');
    o.textContent=i; o.value=i; if(i===fps) o.selected=true;
    sel.appendChild(o);
  }
}

/* ---------- canvas helpers ---------- */
function resizeCanvas(){
  const box=$('canvas-box'),canvas=$('warehouse');
  const controlsH=$('controls').offsetHeight+$('legend').offsetHeight+32;
  const h=box.clientHeight-controlsH, w=box.clientWidth-32;
  const asp=3/2; let cw=w, ch=cw/asp; if(ch>h){ch=h; cw=ch*asp;}
  canvas.width=cw; canvas.height=ch;
}
function startTimer(){clearInterval(timer); timer=setInterval(()=>step(1),1000/fps);}
function togglePlay(){playing=!playing; $('play').textContent=playing?'Pause':'Play'; playing?startTimer():clearInterval(timer);}
function step(d){current=Math.max(0,Math.min(frames.length-1,current+d)); $('time-slider').value=current; drawFrame(current);}
function zoneColor(type,ratio){
  if(type==='storage'){const c=Math.round(255*(1-ratio)); return`rgb(${c},${c},255)`;}
  const s=getComputedStyle(document.documentElement);
  if(type==='dock_in') return s.getPropertyValue('--dock-in');
  if(type==='dock_out')return s.getPropertyValue('--dock-out');
  return s.getPropertyValue('--buffer');
}

/* ---------- draw ---------- */
function drawFrame(i){
  const f=frames[i],c=$('warehouse'),ctx=c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);

  const maxX=Math.max(...layout.map(z=>z.x+(z.w||1)));
  const maxY=Math.max(...layout.map(z=>z.y+(z.h||1)));
  const sc=Math.min(c.width/(maxX+1),c.height/(maxY+1));

  /* zones */
  layout.forEach(z=>{
    const qty=f.zones[z.id]||0, ratio=z.capacity?Math.min(qty/z.capacity,1):0;
    ctx.fillStyle=zoneColor(z.type,ratio);
    ctx.fillRect(z.x*sc,z.y*sc,z.w*sc,z.h*sc);
    ctx.strokeStyle='#3332'; ctx.strokeRect(z.x*sc,z.y*sc,z.w*sc,z.h*sc);

    /* адаптивный шрифт для подписи */
    const maxFont=z.w*sc*0.6;
    const font=Math.max(8,Math.min(maxFont,28));
    ctx.fillStyle='#111';
    ctx.font=`${font}px Inter, sans-serif`;
    ctx.textAlign='center'; ctx.textBaseline='middle';
    ctx.fillText(z.id,(z.x+z.w/2)*sc,(z.y+z.h/2)*sc);
  });

  /* workers → grouped */
  const g={};
  f.workers.forEach(w=>(g[w.zone_id]??=[]).push(w));
  const s=getComputedStyle(document.documentElement);
  const wColor=s.getPropertyValue('--worker').trim();

  Object.entries(g).forEach(([zid,arr])=>{
    const z=zoneMap[zid]; if(!z) return;
    const cx=(z.x+z.w/2)*sc, cy=(z.y+z.h/2)*sc;
    const r=Math.min(z.w,z.h)*sc*0.4;               // чуть больше радиус
    arr.forEach((w,j)=>{
      const ang=2*Math.PI*j/arr.length;
      const wx=cx+r*Math.cos(ang), wy=cy+r*Math.sin(ang);

      /* точка */
      ctx.beginPath(); ctx.fillStyle=wColor;
      ctx.arc(wx,wy,4,0,Math.PI*2); ctx.fill();

      /* подсвета‑фон + ID сверху */
      ctx.font='10px Inter, sans-serif';
      const txt=w.id??'';
      const pad=2, tw=ctx.measureText(txt).width;
      ctx.fillStyle='#fff'; ctx.fillRect(wx-tw/2-pad,wy-16,tw+pad*2,12);
      ctx.strokeStyle='#0001'; ctx.strokeRect(wx-tw/2-pad,wy-16,tw+pad*2,12);

      ctx.fillStyle='#000'; ctx.textAlign='center'; ctx.textBaseline='middle';
      ctx.fillText(txt,wx,wy-10);
    });
  });

  if(f.metrics.incidents>0){
    ctx.fillStyle='#d32f2f'; ctx.font='18px sans-serif';
    ctx.fillText('✖',c.width-24,24);
  }
  $('metric-load').textContent     =(f.metrics.load_pct*100).toFixed(1)+'%';
  $('metric-otif').textContent     =(f.metrics.otif_pct*100).toFixed(1)+'%';
  $('metric-util').textContent     =(f.metrics.util_workers*100).toFixed(1)+'%';
  $('metric-stockouts').textContent=f.metrics.stockouts;
  $('metric-incidents').textContent = f.metrics.incidents;

  $('metric-dq').textContent    = f.metrics.dock_queue ?? '-';
  $('metric-dbs').textContent   = f.metrics.dock_busy_sec ?? '-';

  $('metric-th').textContent    = f.metrics.throughput_lph?.toFixed(1) ?? '-';
  $('metric-done').textContent  = f.metrics.done_lines ?? '-';
  $('metric-lat').textContent   = f.metrics.avg_line_latency_sec ?? '-';
  $('metric-wait').textContent  = f.metrics.waiting_lines ?? '-';
  $('metric-waves').textContent = f.metrics.waves_active ?? '-';
  $('metric-build').textContent = f.metrics.building_wave_size ?? '-';
}
