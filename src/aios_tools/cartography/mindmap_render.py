"""Mind-map specific SVG and interactive WebGPU/Canvas exports."""
from __future__ import annotations

import json
from html import escape
from typing import Any


def _path_d(points: list[list[float]]) -> str:
    (x0,y0),(x1,y1),(x2,y2),(x3,y3)=points
    return f"M{x0},{y0} C{x1},{y1} {x2},{y2} {x3},{y3}"


def render_mindmap_svg(scene: dict[str, Any]) -> str:
    width,height=int(scene["width"]),int(scene["height"])
    parts=[
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        f'<title>{escape(scene.get("title","AIOS System Mind Map"))}</title>',
        '<defs><filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
        '<rect width="100%" height="100%" fill="#071018"/>',
        f'<text x="48" y="48" fill="#edf6fb" font-family="ui-monospace,monospace" font-size="24" font-weight="700">{escape(scene.get("title","AIOS System Mind Map"))}</text>',
        f'<text x="48" y="70" fill="#91a8ba" font-family="ui-monospace,monospace" font-size="11">identity {scene.get("identity_summary",{}).get("resolved_count",0)} · drift {scene.get("drift_summary",{}).get("drift_count",0)} · deterministic radial layout</text>',
    ]
    for edge in scene.get("edges",[]):
        style=edge.get("style",{}); dash=style.get("dash",[])
        dash_attr=f' stroke-dasharray="{" ".join(map(str,dash))}"' if dash else ""
        parts.append(f'<path d="{_path_d(edge["path"])}" fill="none" stroke="{style.get("stroke","#657b91")}" stroke-width="{style.get("width",2)}"{dash_attr} opacity=".88" data-edge-id="{escape(edge["edge_id"])}"><title>{escape(edge["relation_type"])}</title></path>')
    for node in scene.get("nodes",[]):
        r,g,b=node["accent_rgb"]; accent=f"rgb({r},{g},{b})"; x,y,w,h=node["x"],node["y"],node["width"],node["height"]
        stroke=4 if node.get("is_root") else 2
        parts.append(f'<g data-node-id="{escape(node["node_id"])}" data-depth="{node.get("depth",0)}">')
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{22 if node.get("is_root") else 14}" fill="#0d1a25" stroke="{accent}" stroke-width="{stroke}"{(" filter=\"url(#glow)\"" if node.get("is_root") else "")}><title>{escape(node.get("source_pointer",""))}</title></rect>')
        lines=node.get("label_lines") or [node.get("label","")]
        start=y+h/2-(len(lines)-1)*9
        for index,line in enumerate(lines):
            parts.append(f'<text x="{x+w/2}" y="{start+index*20}" text-anchor="middle" fill="#edf6fb" font-family="ui-sans-serif,system-ui" font-size="{16 if node.get("is_root") else 13}" font-weight="650">{escape(line)}</text>')
        parts.append(f'<text x="{x+w/2}" y="{y+h-12}" text-anchor="middle" fill="#91a8ba" font-family="ui-monospace,monospace" font-size="9">{escape(node.get("source_system",""))} · {escape(node.get("authority_role",""))}</text></g>')
    parts.append('</svg>')
    return "\n".join(parts)+"\n"


def render_mindmap_webgpu_html(scene: dict[str, Any]) -> str:
    payload=json.dumps(scene,sort_keys=True,separators=(",",":")).replace("</","<\\/")
    title=escape(scene.get("title","AIOS System Mind Map"))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{title}</title><style>
:root{{color-scheme:dark;font-family:Inter,system-ui,sans-serif}}*{{box-sizing:border-box}}body{{margin:0;overflow:hidden;background:#071018;color:#edf6fb}}header{{position:fixed;z-index:4;inset:max(10px,env(safe-area-inset-top)) 10px auto 10px;display:flex;gap:8px;align-items:center;padding:10px 12px;border:1px solid #244052;border-radius:13px;background:rgba(7,16,24,.9);backdrop-filter:blur(14px)}}header strong{{margin-right:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}button{{border:1px solid #31566e;color:#d9edf8;background:#102432;border-radius:8px;padding:7px 9px}}canvas{{position:fixed;inset:0;width:100vw;height:100vh;touch-action:none}}#gpu{{z-index:1}}#map{{z-index:2}}#tip{{position:fixed;z-index:5;display:none;max-width:min(380px,80vw);pointer-events:none;padding:9px 11px;border:1px solid #39566a;border-radius:10px;background:rgba(5,13,20,.96);font:12px ui-monospace;white-space:pre-wrap}}</style></head><body>
<header><strong>{title}</strong><span id="status"></span><button id="fit">Fit</button><button id="depth">Depth 4</button></header><canvas id="gpu"></canvas><canvas id="map"></canvas><div id="tip"></div><script id="scene" type="application/json">{payload}</script><script>
const scene=JSON.parse(document.getElementById('scene').textContent),gpuCanvas=document.getElementById('gpu'),canvas=document.getElementById('map'),tip=document.getElementById('tip'),status=document.getElementById('status');let camera={{x:0,y:0,zoom:1}},drag=false,px=0,py=0,gpu=null,maxDepth=scene.max_depth||4;
function resize(){{const w=Math.max(1,innerWidth*devicePixelRatio),h=Math.max(1,innerHeight*devicePixelRatio);canvas.width=gpuCanvas.width=w;canvas.height=gpuCanvas.height=h;if(gpu)gpu.context.configure({{device:gpu.device,format:gpu.format,alphaMode:'opaque'}});fitScene();draw()}}function fitScene(){{const p=scene.mobile_fit?.padding||24;camera.zoom=Math.min((canvas.width-p*2)/scene.width,(canvas.height-p*2)/scene.height)*.96;camera.x=(canvas.width-scene.width*camera.zoom)/2;camera.y=(canvas.height-scene.height*camera.zoom)/2}}const world=(x,y)=>[((x*devicePixelRatio)-camera.x)/camera.zoom,((y*devicePixelRatio)-camera.y)/camera.zoom];
function visible(n){{return (n.depth||0)<=maxDepth}}function curve(c,p){{c.beginPath();c.moveTo(p[0][0],p[0][1]);c.bezierCurveTo(p[1][0],p[1][1],p[2][0],p[2][1],p[3][0],p[3][1]);c.stroke()}}function drawOverlay(){{const c=canvas.getContext('2d');c.setTransform(1,0,0,1,0,0);c.clearRect(0,0,canvas.width,canvas.height);if(!gpu){{c.fillStyle='#071018';c.fillRect(0,0,canvas.width,canvas.height)}}c.setTransform(camera.zoom,0,0,camera.zoom,camera.x,camera.y);c.lineCap='round';for(const e of scene.edges){{const a=scene.nodes.find(n=>n.node_id===e.source_node_id),b=scene.nodes.find(n=>n.node_id===e.target_node_id);if(!visible(a)||!visible(b))continue;c.strokeStyle=e.style?.stroke||'#657b91';c.lineWidth=e.style?.width||2;c.setLineDash(e.style?.dash||[]);curve(c,e.path)}}c.setLineDash([]);for(const n of scene.nodes){{if(!visible(n))continue;const accent=`rgb(${{n.accent_rgb.join(',')}})`;c.beginPath();c.roundRect(n.x,n.y,n.width,n.height,n.is_root?22:14);c.fillStyle='#0d1a25';c.fill();c.strokeStyle=accent;c.lineWidth=n.is_root?4:2;c.stroke();c.fillStyle='#edf6fb';c.textAlign='center';c.font=`${{n.is_root?'700 16px':'600 13px'}} system-ui`;const lines=n.label_lines||[n.label],start=n.y+n.height/2-(lines.length-1)*9;lines.forEach((line,i)=>c.fillText(line,n.x+n.width/2,start+i*20));c.fillStyle='#91a8ba';c.font='9px ui-monospace';c.fillText(n.source_system+' · '+n.authority_role,n.x+n.width/2,n.y+n.height-12)}}}}
async function initGPU(){{if(!navigator.gpu)return false;const a=await navigator.gpu.requestAdapter();if(!a)return false;const device=await a.requestDevice(),context=gpuCanvas.getContext('webgpu'),format=navigator.gpu.getPreferredCanvasFormat();context.configure({{device,format,alphaMode:'opaque'}});gpu={{device,context,format}};return true}}function drawGPU(){{if(!gpu)return;const e=gpu.device.createCommandEncoder(),p=e.beginRenderPass({{colorAttachments:[{{view:gpu.context.getCurrentTexture().createView(),clearValue:{{r:.027,g:.063,b:.094,a:1}},loadOp:'clear',storeOp:'store'}}]}});p.end();gpu.device.queue.submit([e.finish()])}}function draw(){{drawGPU();drawOverlay()}}
canvas.onpointerdown=e=>{{drag=true;px=e.clientX;py=e.clientY;canvas.setPointerCapture(e.pointerId)}};canvas.onpointerup=()=>drag=false;canvas.onpointercancel=()=>drag=false;canvas.onpointermove=e=>{{if(drag){{camera.x+=(e.clientX-px)*devicePixelRatio;camera.y+=(e.clientY-py)*devicePixelRatio;px=e.clientX;py=e.clientY;draw()}}const [x,y]=world(e.clientX,e.clientY),n=scene.nodes.find(n=>visible(n)&&x>=n.x&&x<=n.x+n.width&&y>=n.y&&y<=n.y+n.height);if(n){{tip.style.display='block';tip.style.left=e.clientX+12+'px';tip.style.top=e.clientY+12+'px';tip.textContent=n.label+'\n'+n.node_type+' · depth '+n.depth+'\n'+n.source_pointer}}else tip.style.display='none'}};canvas.onwheel=e=>{{e.preventDefault();const p=world(e.clientX,e.clientY);camera.zoom=Math.max(.18,Math.min(5,camera.zoom*Math.exp(-e.deltaY*.001)));camera.x=e.clientX*devicePixelRatio-p[0]*camera.zoom;camera.y=e.clientY*devicePixelRatio-p[1]*camera.zoom;draw()}};document.getElementById('fit').onclick=()=>{{fitScene();draw()}};document.getElementById('depth').onclick=()=>{{maxDepth=maxDepth<=1?scene.max_depth:maxDepth-1;depth.textContent='Depth '+maxDepth;draw()}};addEventListener('resize',resize);(async()=>{{resize();const ok=await initGPU();status.textContent=ok?'WebGPU':'Canvas';draw()}})();
</script></body></html>'''
