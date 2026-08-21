export const motion = {
  quick: 0.14,
  standard: 0.24,
  settle: 0.36,
  ease: "power2.out",
} as const;

export async function loadGsap() {
  const module = await import("gsap");
  return module.gsap;
}
