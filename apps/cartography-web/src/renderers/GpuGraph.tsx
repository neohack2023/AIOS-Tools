import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import type { LayoutResult, RendererBackend, RuntimeState } from '../types';

interface CameraState {
  x: number;
  y: number;
  zoom: number;
}

interface GpuGraphProps {
  layout: LayoutResult;
  selectedId: string;
  onSelect: (nodeId: string) => void;
  onBackend: (backend: RendererBackend) => void;
  onRuntimeState: (state: RuntimeState, detail?: string) => void;
}

const ROLE_COLORS: Record<string, number> = {
  AUTHORITATIVE: 0x1eaeff,
  DRIVE_SHADOW: 0xffaa00,
  IMPLEMENTATION: 0xad69ff,
  DERIVED_VIEW: 0x40d692,
};

const RELATION_COLORS: Record<string, number> = {
  mirrored_by: 0xad69ff,
  implemented_by: 0x40d692,
  enforced_by: 0x40d692,
  backed_by: 0xffaa00,
};

function cubicPoint(
  t: number,
  [p0, p1, p2, p3]: Array<[number, number]>,
): THREE.Vector3 {
  const mt = 1 - t;
  const x =
    mt ** 3 * p0[0] +
    3 * mt ** 2 * t * p1[0] +
    3 * mt * t ** 2 * p2[0] +
    t ** 3 * p3[0];
  const y =
    mt ** 3 * p0[1] +
    3 * mt ** 2 * t * p1[1] +
    3 * mt * t ** 2 * p2[1] +
    t ** 3 * p3[1];
  return new THREE.Vector3(x, y, 0);
}

function disposeObject(object: THREE.Object3D): void {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.Line) {
      child.geometry.dispose();
      const materials = Array.isArray(child.material) ? child.material : [child.material];
      materials.forEach((material) => material.dispose());
    }
  });
}

export function GpuGraph({
  layout,
  selectedId,
  onSelect,
  onBackend,
  onRuntimeState,
}: GpuGraphProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderRef = useRef<(() => void) | null>(null);
  const contentRef = useRef<THREE.Group | null>(null);
  const [camera, setCamera] = useState<CameraState>({ x: 0, y: 0, zoom: 1 });
  const dragRef = useRef<{ pointerId: number; x: number; y: number } | null>(null);

  const fit = useCallback(() => {
    const shell = shellRef.current;
    if (!shell) return;
    const padding = 54;
    const zoom = Math.max(
      0.12,
      Math.min(2.4, Math.min((shell.clientWidth - padding * 2) / layout.width, (shell.clientHeight - padding * 2) / layout.height)),
    );
    setCamera({
      zoom,
      x: (shell.clientWidth - layout.width * zoom) / 2,
      y: (shell.clientHeight - layout.height * zoom) / 2,
    });
  }, [layout.height, layout.width]);

  useEffect(() => {
    fit();
  }, [fit]);

  useEffect(() => {
    const content = contentRef.current;
    if (!content) return;
    content.position.set(camera.x, camera.y, 0);
    content.scale.set(camera.zoom, camera.zoom, 1);
    renderRef.current?.();
  }, [camera]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const shell = shellRef.current;
    if (!canvas || !shell) return;
    const canvasElement: HTMLCanvasElement = canvas;
    const shellElement: HTMLDivElement = shell;

    let disposed = false;
    let renderer: any;
    let resizeObserver: ResizeObserver | undefined;
    const scene = new THREE.Scene();
    const content = new THREE.Group();
    contentRef.current = content;
    scene.add(content);
    const camera3d = new THREE.OrthographicCamera(0, 1, 0, 1, -100, 100);
    camera3d.position.z = 10;

    const drawScene = () => {
      for (const edge of layout.edges) {
        const points = Array.from({ length: 25 }, (_, index) => cubicPoint(index / 24, edge.points));
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const color = RELATION_COLORS[edge.relation_type] ?? 0x4f7389;
        const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9 });
        const line = new THREE.Line(geometry, material);
        line.position.z = 0;
        content.add(line);
      }

      for (const node of layout.nodes) {
        const geometry = new THREE.PlaneGeometry(node.width, node.height);
        const selected = node.node_id === selectedId;
        const material = new THREE.MeshBasicMaterial({
          color: selected ? 0x173a50 : 0x0d1a25,
          transparent: true,
          opacity: 0.98,
          side: THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.set(node.x + node.width / 2, node.y + node.height / 2, 1);
        mesh.userData.nodeId = node.node_id;
        content.add(mesh);

        const border = new THREE.LineSegments(
          new THREE.EdgesGeometry(geometry),
          new THREE.LineBasicMaterial({
            color: ROLE_COLORS[node.authority_role] ?? 0x7891aa,
            transparent: true,
            opacity: selected ? 1 : 0.86,
          }),
        );
        border.position.copy(mesh.position);
        border.position.z = 2;
        border.scale.set(selected ? 1.035 : 1, selected ? 1.08 : 1, 1);
        content.add(border);
      }
    };

    const sizeRenderer = () => {
      if (!renderer || disposed) return;
      const width = Math.max(1, shellElement.clientWidth);
      const height = Math.max(1, shellElement.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(width, height, false);
      camera3d.left = 0;
      camera3d.right = width;
      camera3d.top = 0;
      camera3d.bottom = height;
      camera3d.updateProjectionMatrix();
      renderRef.current?.();
    };

    async function initialize() {
      onBackend('initializing');
      onRuntimeState('loading');
      drawScene();
      let backend: RendererBackend = 'webgl2';
      let fallbackDetail = '';

      const gpuAvailable = 'gpu' in navigator;
      if (gpuAvailable) {
        try {
          const module = await import('three/webgpu');
          renderer = new module.WebGPURenderer({ canvas: canvasElement, antialias: true, alpha: false });
          await renderer.init();
          backend = 'webgpu';
          const device = renderer.backend?.device;
          if (device?.lost) {
            void device.lost.then((info: { message?: string }) => {
              if (!disposed) onRuntimeState('context-lost', info.message || 'WebGPU device lost');
            });
          }
        } catch (error) {
          fallbackDetail = error instanceof Error ? error.message : 'WebGPU initialization failed';
        }
      } else {
        fallbackDetail = 'WebGPU unavailable in this browser';
      }

      if (!renderer) {
        renderer = new THREE.WebGLRenderer({ canvas: canvasElement, antialias: true, alpha: false, powerPreference: 'high-performance' });
        backend = 'webgl2';
      }
      if (disposed) {
        renderer.dispose();
        return;
      }

      renderer.setClearColor(0x071018, 1);
      renderRef.current = () => renderer.render(scene, camera3d);
      onBackend(backend);
      onRuntimeState(backend === 'webgl2' && fallbackDetail ? 'fallback' : 'ready', fallbackDetail || undefined);
      sizeRenderer();
      resizeObserver = new ResizeObserver(sizeRenderer);
      resizeObserver.observe(shellElement);
    }

    const handleContextLost = (event: Event) => {
      event.preventDefault();
      onRuntimeState('context-lost', 'WebGL context lost');
    };
    const handleContextRestored = () => onRuntimeState('loading', 'Graphics context restored; rebuilding view');
    canvasElement.addEventListener('webglcontextlost', handleContextLost);
    canvasElement.addEventListener('webglcontextrestored', handleContextRestored);

    void initialize().catch((error) => {
      onBackend('dom');
      onRuntimeState('error', error instanceof Error ? error.message : 'Renderer initialization failed');
    });

    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      canvasElement.removeEventListener('webglcontextlost', handleContextLost);
      canvasElement.removeEventListener('webglcontextrestored', handleContextRestored);
      renderRef.current = null;
      contentRef.current = null;
      disposeObject(scene);
      renderer?.dispose?.();
    };
  }, [layout, onBackend, onRuntimeState, selectedId]);

  const labelTransform = useMemo(
    () => `translate3d(${camera.x}px, ${camera.y}px, 0) scale(${camera.zoom})`,
    [camera],
  );

  return (
    <div className="gpu-shell" ref={shellRef} data-testid="gpu-shell">
      <canvas
        ref={canvasRef}
        className="gpu-canvas"
        aria-label="GPU-rendered graph geometry"
        onPointerDown={(event) => {
          dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          if (!drag || drag.pointerId !== event.pointerId) return;
          const dx = event.clientX - drag.x;
          const dy = event.clientY - drag.y;
          dragRef.current = { ...drag, x: event.clientX, y: event.clientY };
          setCamera((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
        }}
        onPointerUp={(event) => {
          dragRef.current = null;
          event.currentTarget.releasePointerCapture(event.pointerId);
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
        onWheel={(event) => {
          event.preventDefault();
          const factor = Math.exp(-event.deltaY * 0.0012);
          setCamera((current) => ({ ...current, zoom: Math.max(0.12, Math.min(5, current.zoom * factor)) }));
        }}
      />
      <div className="graph-label-layer" style={{ transform: labelTransform }}>
        {layout.nodes.map((node) => (
          <button
            className={`graph-node-label ${node.node_id === selectedId ? 'is-selected' : ''}`}
            key={node.node_id}
            style={{ left: node.x, top: node.y, width: node.width, height: node.height }}
            type="button"
            onClick={() => onSelect(node.node_id)}
            aria-pressed={node.node_id === selectedId}
          >
            <span>{node.label}</span>
            <small>{node.source_system} · {node.authority_role}</small>
          </button>
        ))}
      </div>
      <button className="fit-button" type="button" onClick={fit}>Fit view</button>
    </div>
  );
}
