"""Standalone interactive WebGPU viewer generation for Cartography scenes."""
from __future__ import annotations

import json
from html import escape
from typing import Any


def render_webgpu_html(scene: dict[str, Any], *, title: str = "AIOS Cartography") -> str:
    """Return a self-contained read-only WebGPU viewer with Canvas2D fallback."""
    payload = json.dumps(scene, sort_keys=True, separators=(",", ":")).replace("</", "<\\/")
    safe_title = escape(title)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter,ui-sans-serif,system-ui,sans-serif; }}
* {{ box-sizing:border-box; }} body {{ margin:0;overflow:hidden;background:#071018;color:#edf6fb; }}
header {{ position:fixed;z-index:4;inset:16px 16px auto 16px;display:flex;gap:10px;align-items:center;padding:12px 14px;border:1px solid #244052;border-radius:14px;background:rgba(7,16,24,.86);backdrop-filter:blur(14px); }}
header strong {{ margin-right:auto; }} button {{ border:1px solid #31566e;color:#d9edf8;background:#102432;border-radius:9px;padding:8px 11px;cursor:pointer; }} button:hover {{ background:#183447; }}
canvas {{ position:fixed;inset:0;display:block;width:100vw;height:100vh;touch-action:none; }} #map {{ z-index:2; }} #gpu {{ z-index:1; }}
#tip {{ position:fixed;z-index:5;display:none;max-width:360px;pointer-events:none;padding:10px 12px;border:1px solid #39566a;border-radius:10px;background:rgba(5,13,20,.95);font-size:12px;line-height:1.45;white-space:pre-wrap; }}
#status {{ color:#8ba6b7;font:12px ui-monospace,monospace; }}
</style></head><body>
<header><strong>{safe_title}</strong><span id="status">initializing</span><button id="reset">Reset</button><button id="svg">Export SVG</button><button id="png">Export PNG</button></header>
<canvas id="gpu"></canvas><canvas id="map"></canvas><div id="tip"></div>
<script id="scene" type="application/json">{payload}</script><script>
const scene=JSON.parse(document.getElementById('scene').textContent), gpuCanvas=document.getElementById('gpu'), canvas=document.getElementById('map'), tip=document.getElementById('tip'), status=document.getElementById('status');
const camera={{x:0,y:0,zoom:1}}; let dragging=false,px=0,py=0,gpu=null;
function resize(){{const w=Math.max(1,innerWidth*devicePixelRatio),h=Math.max(1,innerHeight*devicePixelRatio);canvas.width=gpuCanvas.width=w;canvas.height=gpuCanvas.height=h;if(gpu)gpu.context.configure({{device:gpu.device,format:gpu.format,alphaMode:'opaque'}});draw();}}
const world=(x,y)=>[((x*devicePixelRatio)-camera.x)/camera.zoom,((y*devicePixelRatio)-camera.y)/camera.zoom];
function fit(){{camera.zoom=Math.min(canvas.width/scene.width,canvas.height/scene.height)*.88;camera.x=(canvas.width-scene.width*camera.zoom)/2;camera.y=(canvas.height-scene.height*camera.zoom)/2;}}
function drawOverlay(){{const c=canvas.getContext('2d');c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,canvas.width,canvas.height);if(!gpu){{c.fillStyle='#071018';c.fillRect(0,0,canvas.width,canvas.height);}}c.setTransform(camera.zoom,0,0,camera.zoom,camera.x,camera.y);c.lineJoin='round';c.lineCap='round';for(const e of scene.edges){{c.strokeStyle='#657b91';c.lineWidth=2;c.beginPath();e.points.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.stroke();}}for(const n of scene.nodes){{const accent=`rgb(${{n.accent_rgb.join(',')}})`;c.beginPath();c.roundRect(n.x,n.y,n.width,n.height,12);c.fillStyle='#0d1a25';c.fill();c.strokeStyle=accent;c.lineWidth=2;c.stroke();c.fillStyle=accent;c.fillRect(n.x,n.y,6,n.height);c.fillStyle='#edf6fb';c.font='600 14px system-ui';c.fillText(n.label.slice(0,32),n.x+18,n.y+30);c.fillStyle='#91a8ba';c.font='10px ui-monospace,monospace';c.fillText(`${{n.source_system}} · ${{n.authority_role}}`.slice(0,48),n.x+18,n.y+52);}}}}
async function initGPU(){{if(!navigator.gpu)return false;const adapter=await navigator.gpu.requestAdapter();if(!adapter)return false;const device=await adapter.requestDevice(),context=gpuCanvas.getContext('webgpu'),format=navigator.gpu.getPreferredCanvasFormat();context.configure({{device,format,alphaMode:'opaque'}});gpu={{device,context,format}};return true;}}
function drawGPU(){{if(!gpu)return;const encoder=gpu.device.createCommandEncoder(),pass=encoder.beginRenderPass({{colorAttachments:[{{view:gpu.context.getCurrentTexture().createView(),clearValue:{{r:.027,g:.063,b:.094,a:1}},loadOp:'clear',storeOp:'store'}}]}});pass.end();gpu.device.queue.submit([encoder.finish()]);}}
function draw(){{drawGPU();drawOverlay();}}
canvas.addEventListener('pointerdown',e=>{{dragging=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId);}});canvas.addEventListener('pointermove',e=>{{if(dragging){{camera.x+=(e.clientX-px)*devicePixelRatio;camera.y+=(e.clientY-py)*devicePixelRatio;px=e.clientX;py=e.clientY;draw();}}const [x,y]=world(e.clientX,e.clientY),n=scene.nodes.find(n=>x>=n.x&&x<=n.x+n.width&&y>=n.y&&y<=n.y+n.height);if(n){{tip.style.display='block';tip.style.left=e.clientX+14+'px';tip.style.top=e.clientY+14+'px';tip.textContent=`${{n.label}}\n${{n.node_type}} · ${{n.authority_role}}\n${{n.source_pointer}}`;}}else tip.style.display='none';}});canvas.addEventListener('pointerup',()=>dragging=false);canvas.addEventListener('pointercancel',()=>dragging=false);canvas.addEventListener('wheel',e=>{{e.preventDefault();const p=world(e.clientX,e.clientY);camera.zoom=Math.max(.15,Math.min(5,camera.zoom*Math.exp(-e.deltaY*.001)));camera.x=e.clientX*devicePixelRatio-p[0]*camera.zoom;camera.y=e.clientY*devicePixelRatio-p[1]*camera.zoom;draw();}},{{passive:false}});
document.getElementById('reset').onclick=()=>{{fit();draw();}};document.getElementById('png').onclick=()=>{{const out=document.createElement('canvas');out.width=canvas.width;out.height=canvas.height;const c=out.getContext('2d');c.fillStyle='#071018';c.fillRect(0,0,out.width,out.height);c.drawImage(canvas,0,0);const a=document.createElement('a');a.download=scene.view_id+'.png';a.href=out.toDataURL('image/png');a.click();}};document.getElementById('svg').onclick=()=>{{const q=s=>String(s).replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));const lines=['<svg xmlns="http://www.w3.org/2000/svg" width="'+scene.width+'" height="'+scene.height+'" viewBox="0 0 '+scene.width+' '+scene.height+'">','<rect width="100%" height="100%" fill="#071018"/>'];for(const e of scene.edges)lines.push('<polyline points="'+e.points.map(p=>p.join(',')).join(' ')+'" fill="none" stroke="#657b91" stroke-width="2"/>');for(const n of scene.nodes){{lines.push('<rect x="'+n.x+'" y="'+n.y+'" width="'+n.width+'" height="'+n.height+'" rx="12" fill="#0d1a25" stroke="rgb('+n.accent_rgb.join(',')+')" stroke-width="2"/>');lines.push('<text x="'+(n.x+18)+'" y="'+(n.y+30)+'" fill="#edf6fb" font-family="system-ui" font-size="14">'+q(n.label.slice(0,32))+'</text>');}}lines.push('</svg>');const blob=new Blob([lines.join('\n')],{{type:'image/svg+xml'}}),a=document.createElement('a');a.download=scene.view_id+'.svg';a.href=URL.createObjectURL(blob);a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}};
addEventListener('resize',resize);(async()=>{{resize();fit();const ok=await initGPU();status.textContent=ok?'WebGPU surface + deterministic overlay':'Canvas2D fallback';draw();}})();
</script></body></html>'''
