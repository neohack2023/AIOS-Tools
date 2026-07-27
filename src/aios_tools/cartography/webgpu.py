"""Standalone interactive WebGPU viewer generation for Cartography scenes."""
from __future__ import annotations

import json
from html import escape
from typing import Any


def render_webgpu_html(scene: dict[str, Any], *, title: str = "AIOS Cartography") -> str:
    """Return a self-contained HTML viewer with WebGPU and Canvas2D fallback.

    The embedded scene is immutable JSON. Interaction changes camera state only;
    source snapshots, identity bindings, and drift results remain untouched.
    """
    payload = json.dumps(scene, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    safe_title = escape(title)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; overflow: hidden; background: #071018; color: #edf6fb; }}
header {{ position: fixed; z-index: 4; inset: 16px 16px auto 16px; display: flex; gap: 10px; align-items: center; padding: 12px 14px; border: 1px solid #244052; border-radius: 14px; background: rgba(7,16,24,.86); backdrop-filter: blur(14px); }}
header strong {{ margin-right: auto; }}
button {{ border: 1px solid #31566e; color: #d9edf8; background: #102432; border-radius: 9px; padding: 8px 11px; cursor: pointer; }}
button:hover {{ background: #183447; }}
canvas {{ display: block; width: 100vw; height: 100vh; touch-action: none; }}
#tip {{ position: fixed; z-index: 5; display: none; max-width: 360px; pointer-events: none; padding: 10px 12px; border: 1px solid #39566a; border-radius: 10px; background: rgba(5,13,20,.95); font-size: 12px; line-height: 1.45; white-space: pre-wrap; }}
#status {{ color: #8ba6b7; font: 12px ui-monospace, monospace; }}
</style>
</head>
<body>
<header><strong>{safe_title}</strong><span id="status">initializing</span><button id="reset">Reset</button><button id="svg">Export SVG</button><button id="png">Export PNG</button></header>
<canvas id="map"></canvas><div id="tip"></div>
<script id="scene" type="application/json">{payload}</script>
<script>
const scene = JSON.parse(document.getElementById('scene').textContent);
const canvas = document.getElementById('map');
const tip = document.getElementById('tip');
const status = document.getElementById('status');
const camera = {{x: 0, y: 0, zoom: 1}};
let dragging = false, px = 0, py = 0;
const resize = () => {{ canvas.width = Math.max(1, innerWidth * devicePixelRatio); canvas.height = Math.max(1, innerHeight * devicePixelRatio); draw(); }};
const world = (clientX, clientY) => [((clientX*devicePixelRatio)-camera.x)/camera.zoom, ((clientY*devicePixelRatio)-camera.y)/camera.zoom];
function fit() {{
  const sx = canvas.width / scene.width, sy = canvas.height / scene.height;
  camera.zoom = Math.min(sx, sy) * .88;
  camera.x = (canvas.width - scene.width * camera.zoom) / 2;
  camera.y = (canvas.height - scene.height * camera.zoom) / 2;
}}
function rounded(ctx,x,y,w,h,r) {{ ctx.beginPath(); ctx.roundRect(x,y,w,h,r); }}
function draw2d() {{
  const ctx = canvas.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0); ctx.fillStyle='#071018'; ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.setTransform(camera.zoom,0,0,camera.zoom,camera.x,camera.y);
  ctx.lineJoin='round'; ctx.lineCap='round';
  for (const edge of scene.edges) {{
    ctx.strokeStyle='#657b91'; ctx.lineWidth=2; ctx.beginPath();
    edge.points.forEach((p,i)=> i ? ctx.lineTo(p[0],p[1]) : ctx.moveTo(p[0],p[1])); ctx.stroke();
  }}
  for (const node of scene.nodes) {{
    const c=`rgb(${{node.accent_rgb.join(',')}})`;
    rounded(ctx,node.x,node.y,node.width,node.height,12); ctx.fillStyle='#0d1a25'; ctx.fill(); ctx.strokeStyle=c; ctx.lineWidth=2; ctx.stroke();
    ctx.fillStyle=c; ctx.fillRect(node.x,node.y,6,node.height);
    ctx.fillStyle='#edf6fb'; ctx.font='600 14px system-ui'; ctx.fillText(node.label.slice(0,32),node.x+18,node.y+30);
    ctx.fillStyle='#91a8ba'; ctx.font='10px ui-monospace,monospace'; ctx.fillText(`${{node.source_system}} · ${{node.authority_role}}`.slice(0,48),node.x+18,node.y+52);
  }}
}}
let gpu = null;
async function initWebGPU() {{
  if (!navigator.gpu) return false;
  const adapter = await navigator.gpu.requestAdapter(); if (!adapter) return false;
  const device = await adapter.requestDevice();
  const context = canvas.getContext('webgpu');
  const format = navigator.gpu.getPreferredCanvasFormat();
  context.configure({{device,format,alphaMode:'opaque'}});
  gpu = {{device,context,format}};
  return true;
}}
function drawGPUBackground() {{
  if (!gpu) return false;
  const encoder=gpu.device.createCommandEncoder();
  const pass=encoder.beginRenderPass({{colorAttachments:[{{view:gpu.context.getCurrentTexture().createView(),clearValue:{{r:.027,g:.063,b:.094,a:1}},loadOp:'clear',storeOp:'store'}}]}}); pass.end(); gpu.device.queue.submit([encoder.finish()]);
  return true;
}}
function draw() {{
  // WebGPU owns the presentation surface when available. The deterministic map
  // primitives are then drawn by the portable overlay path for text fidelity.
  if (gpu) drawGPUBackground();
  draw2d();
}}
canvas.addEventListener('pointerdown',e=>{{dragging=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId);}});
canvas.addEventListener('pointermove',e=>{{
  if(dragging){{camera.x+=(e.clientX-px)*devicePixelRatio;camera.y+=(e.clientY-py)*devicePixelRatio;px=e.clientX;py=e.clientY;draw();}}
  const [x,y]=world(e.clientX,e.clientY); const node=scene.nodes.find(n=>x>=n.x&&x<=n.x+n.width&&y>=n.y&&y<=n.y+n.height);
  if(node){{tip.style.display='block';tip.style.left=(e.clientX+14)+'px';tip.style.top=(e.clientY+14)+'px';tip.textContent=`${{node.label}}\n${{node.node_type}} · ${{node.authority_role}}\n${{node.source_pointer}}`;}} else tip.style.display='none';
}});
canvas.addEventListener('pointerup',()=>dragging=false); canvas.addEventListener('pointercancel',()=>dragging=false);
canvas.addEventListener('wheel',e=>{{e.preventDefault();const before=world(e.clientX,e.clientY);camera.zoom=Math.max(.15,Math.min(5,camera.zoom*Math.exp(-e.deltaY*.001)));camera.x=e.clientX*devicePixelRatio-before[0]*camera.zoom;camera.y=e.clientY*devicePixelRatio-before[1]*camera.zoom;draw();}},{{passive:false}});
document.getElementById('reset').onclick=()=>{{fit();draw();}};
document.getElementById('png').onclick=()=>{{const a=document.createElement('a');a.download=`${{scene.view_id}}.png`;a.href=canvas.toDataURL('image/png');a.click();}};
document.getElementById('svg').onclick=()=>{{
 const lines=['<svg xmlns="http://www.w3.org/2000/svg" width="'+scene.width+'" height="'+scene.height+'" viewBox="0 0 '+scene.width+' '+scene.height+'">','<rect width="100%" height="100%" fill="#071018"/>'];
 for(const e of scene.edges) lines.push('<polyline points="'+e.points.map(p=>p.join(',')).join(' ')+'" fill="none" stroke="#657b91" stroke-width="2"/>');
 for(const n of scene.nodes) lines.push('<rect x="'+n.x+'" y="'+n.y+'" width="'+n.width+'" height="'+n.height+'" rx="12" fill="#0d1a25" stroke="rgb('+n.accent_rgb.join(',')+')" stroke-width="2"/>');
 lines.push('</svg>'); const blob=new Blob([lines.join('\n')],{{type:'image/svg+xml'}}); const a=document.createElement('a');a.download=scene.view_id+'.svg';a.href=URL.createObjectURL(blob);a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}};
addEventListener('resize',resize);
(async()=>{{resize();fit();const ok=await initWebGPU();status.textContent=ok?'WebGPU + deterministic overlay':'Canvas2D fallback';draw();}})();
</script>
</body>
</html>'''
