import { useEffect, useRef, useState } from "react";
import type * as Three from "three";

import { loadGsap, motion } from "@/lib/motion";
import type { SearchJobState } from "@/lib/search-job-state";

type Runtime = {
  renderer: Three.WebGLRenderer;
  scene: Three.Scene;
  camera: Three.PerspectiveCamera;
  nodes: Map<string, Three.Mesh>;
  lines: Three.Line[];
  module: typeof import("three");
  render: () => void;
};

const terminal = new Set(["completed", "partial", "failed", "cancelled"]);
const colors = {
  idle: 0x75818a,
  selected: 0x75818a,
  searching: 0x1d778c,
  completed: 0x2c8068,
  degraded: 0xb67829,
  failed: 0xb84c48,
  skipped: 0x75818a,
  memory: 0x647eaa,
  core: 0x294d59,
};

function StaticFallback({ state }: { state: SearchJobState }) {
  return (
    <div className="grid h-28 place-items-center border-y bg-muted/20" data-testid="webgl-fallback">
      <div className="flex flex-wrap items-center justify-center gap-2 text-[10px] text-muted-foreground">
        {Object.entries(state.sources).map(([source, item]) => (
          <span key={source} className="border-b pb-0.5" dir="ltr">
            {source} · {item.status}
          </span>
        ))}
        {state.memory.status !== "idle" && <span>Local memory · {state.memory.status}</span>}
      </div>
    </div>
  );
}

export default function RetrievalTopology3d({
  state,
  forceFallback = false,
}: {
  state: SearchJobState;
  forceFallback?: boolean;
}) {
  const host = useRef<HTMLDivElement>(null);
  const runtime = useRef<Runtime | null>(null);
  const phase = useRef(state.phase);
  phase.current = state.phase;
  const stateRef = useRef(state);
  stateRef.current = state;
  const [fallback, setFallback] = useState(forceFallback);
  const [ready, setReady] = useState(false);
  const sources = Object.entries(state.sources);
  const nodeSignature = [
    ...sources.map(([source, item]) => `${source}:${item.status}`),
    `memory:${state.memory.status}`,
    `phase:${state.phase}`,
  ].join("|");

  useEffect(() => {
    if (forceFallback || !host.current) return;
    let disposed = false;
    let observer: ResizeObserver | null = null;
    let visibility: (() => void) | null = null;
    let motionPreference: MediaQueryList | null = null;
    let contextLost: ((event: Event) => void) | null = null;
    void import("three")
      .then((THREE) => {
        if (disposed || !host.current) return;
        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.domElement.className = "h-full w-full pointer-events-none";
        renderer.domElement.setAttribute("aria-hidden", "true");
        host.current.append(renderer.domElement);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 20);
        camera.position.set(0, 0, 6.5);
        const value: Runtime = {
          renderer,
          scene,
          camera,
          nodes: new Map(),
          lines: [],
          module: THREE,
          render: () => renderer.render(scene, camera),
        };
        runtime.current = value;
        setReady(true);
        observer = new ResizeObserver(([entry]) => {
          const width = Math.max(1, entry.contentRect.width);
          const height = Math.max(1, entry.contentRect.height);
          renderer.setSize(width, height, false);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
          value.render();
        });
        observer.observe(host.current);
        motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
        visibility = () => {
          if (document.hidden) renderer.setAnimationLoop(null);
          else if (!terminal.has(phase.current) && !motionPreference?.matches)
            renderer.setAnimationLoop(value.render);
          else value.render();
        };
        document.addEventListener("visibilitychange", visibility);
        motionPreference.addEventListener("change", visibility);
        contextLost = (event: Event) => {
          event.preventDefault();
          setFallback(true);
        };
        renderer.domElement.addEventListener("webglcontextlost", contextLost);
        visibility();
        setFallback(false);
      })
      .catch(() => setFallback(true));
    return () => {
      disposed = true;
      observer?.disconnect();
      if (visibility) document.removeEventListener("visibilitychange", visibility);
      if (visibility) motionPreference?.removeEventListener("change", visibility);
      const value = runtime.current;
      if (!value) return;
      if (contextLost) value.renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      value.renderer.setAnimationLoop(null);
      value.nodes.forEach((mesh) => {
        mesh.geometry.dispose();
        const material = mesh.material;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material.dispose();
      });
      value.lines.forEach((line) => {
        line.geometry.dispose();
        const material = line.material;
        if (Array.isArray(material)) material.forEach((item) => item.dispose());
        else material.dispose();
      });
      value.scene.clear();
      value.renderer.dispose();
      value.renderer.domElement.remove();
      runtime.current = null;
    };
  }, [fallback, forceFallback]);

  useEffect(() => {
    const value = runtime.current;
    if (!value || fallback) return;
    const currentState = stateRef.current;
    const currentSources = Object.entries(currentState.sources);
    const { module: THREE, scene } = value;
    value.nodes.forEach((mesh) => {
      mesh.geometry.dispose();
      (mesh.material as Three.Material).dispose();
      scene.remove(mesh);
    });
    value.lines.forEach((line) => {
      line.geometry.dispose();
      (line.material as Three.Material).dispose();
      scene.remove(line);
    });
    value.nodes.clear();
    value.lines = [];
    const entries = currentSources
      .filter(([, item]) => item.status !== "skipped")
      .map(([name, item]) => ({ name, status: item.status }));
    if (currentState.memory.status !== "idle") {
      entries.push({
        name: "local_memory",
        status: currentState.memory.status === "searching" ? "searching" : "completed",
      });
    }
    const target = new THREE.Vector3(0.55, 0, 0);
    const sourceX = -1.7;
    entries.forEach(({ name, status }, index) => {
      const y = entries.length === 1 ? 0 : 1.2 - (index * 2.4) / (entries.length - 1);
      const geometry = new THREE.SphereGeometry(name === "local_memory" ? 0.105 : 0.09, 12, 8);
      const material = new THREE.MeshBasicMaterial({
        color: name === "local_memory" ? colors.memory : colors[status as keyof typeof colors] ?? colors.idle,
        transparent: true,
        opacity: status === "selected" ? 0.55 : 0.92,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(sourceX, y, index % 2 ? -0.16 : 0.16);
      scene.add(mesh);
      value.nodes.set(name, mesh);
      const lineGeometry = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), target.clone()]);
      const line = new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({ color: material.color, transparent: true, opacity: 0.34 }));
      scene.add(line);
      value.lines.push(line);
    });
    const core = new THREE.Mesh(new THREE.RingGeometry(0.2, 0.27, 24), new THREE.MeshBasicMaterial({ color: colors.core, side: THREE.DoubleSide }));
    core.position.copy(target);
    scene.add(core);
    value.nodes.set("mafer", core);
    const evidence = new THREE.Mesh(new THREE.CircleGeometry(0.13, 20), new THREE.MeshBasicMaterial({ color: terminal.has(currentState.phase) ? colors.completed : colors.idle }));
    evidence.position.set(1.72, 0, 0);
    scene.add(evidence);
    value.nodes.set("evidence", evidence);
    const output = new THREE.Line(new THREE.BufferGeometry().setFromPoints([target.clone(), evidence.position.clone()]), new THREE.LineBasicMaterial({ color: colors.core, transparent: true, opacity: 0.5 }));
    scene.add(output);
    value.lines.push(output);
    let disposed = false;
    let revert: () => void = () => undefined;
    void loadGsap().then((gsap) => {
      if (disposed) return;
      const context = gsap.context(() => {
        const media = gsap.matchMedia();
        media.add("(prefers-reduced-motion: no-preference)", () => {
          for (const [name, mesh] of value.nodes) {
            if (name === "mafer" || name === "evidence") continue;
            gsap.fromTo(mesh.scale, { x: 0.72, y: 0.72, z: 0.72 }, { x: 1, y: 1, z: 1, duration: motion.standard, ease: motion.ease });
          }
        });
        revert = () => media.revert();
      });
      const nested = revert;
      revert = () => {
        nested();
        context.revert();
      };
    });
    if (
      terminal.has(currentState.phase) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    )
      value.renderer.setAnimationLoop(null);
    else if (!document.hidden) value.renderer.setAnimationLoop(value.render);
    value.render();
    if (host.current) {
      host.current.dataset.renderCalls = String(value.renderer.info.render.calls);
      host.current.dataset.triangles = String(value.renderer.info.render.triangles);
      host.current.dataset.geometries = String(value.renderer.info.memory.geometries);
      host.current.dataset.textures = String(value.renderer.info.memory.textures);
    }
    return () => {
      disposed = true;
      revert();
    };
  }, [fallback, nodeSignature, ready]);

  if (fallback) return <StaticFallback state={state} />;
  return (
    <div
      ref={host}
      className="h-28 w-full overflow-hidden border-y bg-muted/15"
      data-testid="retrieval-topology-3d"
      aria-label="Data-driven retrieval topology visualization"
    />
  );
}
