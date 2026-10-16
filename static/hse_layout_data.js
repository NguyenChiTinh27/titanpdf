/**
 * static/hse_layout_data.js — Canonical Safety & Fire Protection Equipment Dictionary,
 * Vector SVG Graphics Library (41 Canonical Symbols), Route & Hazard Zone Presets.
 * Sourced & upgraded from HSE Layout Planner & Vision Factory CAD Engine.
 */

(function (window) {
  "use strict";

const SVG_ICONS = {

  /* ===== NHÓM 1: THIẾT BỊ AN TOÀN & Y TẾ (14 Loại) ===== */

  shower: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#059669"/>
    <circle cx="50" cy="22" r="7" fill="#fff"/>
    <line x1="50" y1="29" x2="50" y2="44" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <path d="M26 44h48l-8 14H34Z" fill="#fff"/>
    <line x1="35" y1="64" x2="30" y2="88" stroke="#a7f3d0" stroke-width="4" stroke-linecap="round" stroke-dasharray="3 6"/>
    <line x1="45" y1="64" x2="44" y2="88" stroke="#a7f3d0" stroke-width="4" stroke-linecap="round" stroke-dasharray="3 6"/>
    <line x1="55" y1="64" x2="56" y2="88" stroke="#a7f3d0" stroke-width="4" stroke-linecap="round" stroke-dasharray="3 6"/>
    <line x1="65" y1="64" x2="70" y2="88" stroke="#a7f3d0" stroke-width="4" stroke-linecap="round" stroke-dasharray="3 6"/>
    <path d="M76 34h12v18" stroke="#facc15" stroke-width="5" stroke-linecap="round" fill="none"/>
    <circle cx="88" cy="56" r="4" fill="#facc15"/>
  </svg>`,

  eyewash: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0284c7"/>
    <path d="M20 66c0 16 14 22 30 22s30-6 30-22H20Z" fill="#fff"/>
    <ellipse cx="36" cy="40" rx="10" ry="8" fill="#fff"/>
    <circle cx="36" cy="40" r="5" fill="#0369a1"/>
    <circle cx="38" cy="38" r="2" fill="#fff"/>
    <ellipse cx="64" cy="40" rx="10" ry="8" fill="#fff"/>
    <circle cx="64" cy="40" r="5" fill="#0369a1"/>
    <circle cx="66" cy="38" r="2" fill="#fff"/>
    <path d="M36 62c0-10 5-14 14-14M64 62c0-10-5-14-14-14" stroke="#bae6fd" stroke-width="5" stroke-linecap="round" fill="none"/>
    <path d="M30 32c0-12 8-16 20-16s20 4 20 16" stroke="#facc15" stroke-width="4" fill="none" stroke-dasharray="3 4"/>
  </svg>`,

  map: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#4f46e5"/>
    <rect x="16" y="16" width="68" height="68" rx="8" fill="#fff"/>
    <rect x="22" y="22" width="26" height="26" rx="3" fill="#cbd5e1"/>
    <rect x="52" y="22" width="26" height="16" rx="3" fill="#cbd5e1"/>
    <rect x="52" y="42" width="26" height="36" rx="3" fill="#cbd5e1"/>
    <rect x="22" y="52" width="26" height="26" rx="3" fill="#cbd5e1"/>
    <path d="M42 34l22 22" stroke="#16a34a" stroke-width="5" stroke-linecap="round" stroke-dasharray="3 4" fill="none"/>
    <circle cx="64" cy="56" r="6" fill="#dc2626"/>
    <circle cx="64" cy="56" r="2.5" fill="#fff"/>
  </svg>`,

  assembly: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#15803d"/>
    <circle cx="50" cy="43" r="8" fill="#fff"/>
    <path d="M41 60c0-6 4-9 9-9s9 3 9 9v10H41V60Z" fill="#fff"/>
    <circle cx="32" cy="47" r="6" fill="#dcfce7"/>
    <path d="M25 64c0-5 3-7 7-7s7 2 7 7v6H25V64Z" fill="#dcfce7"/>
    <circle cx="68" cy="47" r="6" fill="#dcfce7"/>
    <path d="M61 64c0-5 3-7 7-7s7 2 7 7v6H61V64Z" fill="#dcfce7"/>
    <path d="M14 14l16 16M14 30V14h16M86 14L70 30M86 30V14H70M14 86l16-16M14 70v16h16M86 86L70 70M86 70v16H70" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`,

  firstaid: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#16a34a"/>
    <rect x="38" y="14" width="24" height="72" rx="6" fill="#fff"/>
    <rect x="14" y="38" width="72" height="24" rx="6" fill="#fff"/>
  </svg>`,

  rescue: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#ea580c"/>
    <rect x="18" y="24" width="64" height="56" rx="8" fill="#fff"/>
    <rect x="34" y="14" width="32" height="12" rx="4" fill="#ffedd5" stroke="#ea580c" stroke-width="3"/>
    <path d="M36 58l14-16 14 16" stroke="#ea580c" stroke-width="7" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <line x1="50" y1="42" x2="50" y2="70" stroke="#ea580c" stroke-width="7" stroke-linecap="round"/>
    <circle cx="50" cy="56" r="4" fill="#fff"/>
  </svg>`,

  spillkit: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#d97706"/>
    <path d="M24 34h52l-7 52H31Z" fill="#fff"/>
    <rect x="20" y="22" width="60" height="12" rx="4" fill="#fef3c7" stroke="#b45309" stroke-width="2"/>
    <polygon points="50,44 68,72 32,72" fill="#dc2626"/>
    <line x1="50" y1="52" x2="50" y2="62" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <circle cx="50" cy="68" r="3.5" fill="#fff"/>
  </svg>`,

  loto: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#dc2626"/>
    <rect x="26" y="42" width="48" height="42" rx="8" fill="#facc15" stroke="#fff" stroke-width="3"/>
    <path d="M36 42V26a14 14 0 0128 0v16" stroke="#fff" stroke-width="7" fill="none" stroke-linecap="round"/>
    <circle cx="50" cy="58" r="5" fill="#dc2626"/>
    <line x1="50" y1="63" x2="50" y2="74" stroke="#dc2626" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  scba: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0284c7"/>
    <rect x="26" y="20" width="20" height="56" rx="10" fill="#facc15" stroke="#fff" stroke-width="3"/>
    <rect x="54" y="20" width="20" height="56" rx="10" fill="#facc15" stroke="#fff" stroke-width="3"/>
    <path d="M36 20V12h28v8" stroke="#fff" stroke-width="4" fill="none"/>
    <circle cx="50" cy="12" r="5" fill="#fff"/>
    <circle cx="50" cy="58" r="14" fill="#fff" fill-opacity="0.3" stroke="#fff" stroke-width="3"/>
  </svg>`,

  stretcher: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0d9488"/>
    <line x1="10" y1="50" x2="90" y2="50" stroke="#fff" stroke-width="8" stroke-linecap="round"/>
    <rect x="20" y="32" width="60" height="36" rx="6" fill="#f97316" stroke="#fff" stroke-width="3"/>
    <rect x="46" y="38" width="8" height="24" rx="2" fill="#fff"/>
    <rect x="38" y="46" width="24" height="8" rx="2" fill="#fff"/>
  </svg>`,

  gasdetector: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#7c3aed"/>
    <rect x="26" y="16" width="48" height="68" rx="10" fill="#fff"/>
    <rect x="34" y="24" width="32" height="22" rx="4" fill="#1e1b4b"/>
    <circle cx="50" cy="35" r="7" fill="#22c55e"/>
    <circle cx="50" cy="35" r="3" fill="#fff"/>
    <path d="M41 32a9 9 0 0018 0" stroke="#4ade80" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <circle cx="50" cy="63" r="9" fill="#7c3aed"/>
    <circle cx="50" cy="63" r="4" fill="#facc15"/>
    <line x1="34" y1="52" x2="66" y2="52" stroke="#e2e8f0" stroke-width="2"/>
  </svg>`,

  estop: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#eab308"/>
    <rect x="16" y="16" width="68" height="68" rx="12" fill="#fff"/>
    <circle cx="50" cy="50" r="26" fill="#dc2626"/>
    <circle cx="50" cy="50" r="18" fill="#ef4444"/>
    <!-- Hand icon: palm up = stop signal -->
    <rect x="46" y="30" width="8" height="22" rx="4" fill="#fff"/>
    <rect x="36" y="36" width="8" height="16" rx="4" fill="#fff"/>
    <rect x="56" y="36" width="8" height="16" rx="4" fill="#fff"/>
    <path d="M34 52h32v6c0 4-3 7-8 7H42c-5 0-8-3-8-7V52Z" fill="#fff"/>
  </svg>`,

  fireblanket: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#ea580c"/>
    <rect x="16" y="16" width="68" height="68" rx="10" fill="#fff"/>
    <rect x="24" y="24" width="52" height="52" rx="6" fill="#f97316"/>
    <line x1="38" y1="76" x2="38" y2="92" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <line x1="62" y1="76" x2="62" y2="92" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <!-- Wave/blanket stripes -->
    <path d="M30 40 Q40 34 50 40 Q60 46 70 40" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>
    <path d="M30 52 Q40 46 50 52 Q60 58 70 52" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>
    <path d="M30 64 Q40 58 50 64 Q60 70 70 64" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>
  </svg>`,

  ppe_station: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0284c7"/>
    <path d="M30 48c0-12 9-20 20-20s20 8 20 20v8H30V48Z" fill="#facc15" stroke="#fff" stroke-width="3"/>
    <rect x="24" y="56" width="52" height="6" rx="3" fill="#facc15" stroke="#fff" stroke-width="2"/>
    <circle cx="38" cy="74" r="9" fill="#fff"/>
    <circle cx="62" cy="74" r="9" fill="#fff"/>
    <line x1="47" y1="74" x2="53" y2="74" stroke="#fff" stroke-width="4"/>
  </svg>`,

  /* ===== NHÓM 2: PHƯƠNG TIỆN & HỆ THỐNG PCCC (16 Loại) ===== */

  callpoint: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#dc2626"/>
    <rect x="18" y="18" width="64" height="64" rx="10" fill="#fff"/>
    <rect x="26" y="26" width="48" height="48" rx="6" fill="#b91c1c"/>
    <circle cx="50" cy="50" r="14" fill="#fff"/>
    <circle cx="50" cy="50" r="7" fill="#dc2626"/>
  </svg>`,

  firebell: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#dc2626"/>
    <path d="M22 68c0-14 8-28 28-28s28 14 28 28H22Z" fill="#fff"/>
    <rect x="42" y="68" width="16" height="14" rx="3" fill="#fff"/>
    <rect x="34" y="20" width="32" height="12" rx="6" fill="#fff"/>
    <line x1="50" y1="20" x2="50" y2="40" stroke="#fff" stroke-width="5"/>
    <circle cx="50" cy="76" r="5" fill="#dc2626"/>
    <path d="M18 24a36 36 0 000 44" stroke="#fef08a" stroke-width="5" stroke-linecap="round" fill="none"/>
    <path d="M82 24a36 36 0 010 44" stroke="#fef08a" stroke-width="5" stroke-linecap="round" fill="none"/>
  </svg>`,

  smoke: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#334155"/>
    <circle cx="50" cy="50" r="32" fill="#fff"/>
    <circle cx="50" cy="50" r="20" fill="#f1f5f9" stroke="#94a3b8" stroke-width="3"/>
    <circle cx="50" cy="50" r="7" fill="#dc2626"/>
    <path d="M38 36c5-6 19-6 24 0" stroke="#64748b" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  </svg>`,

  heat: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#ea580c"/>
    <circle cx="50" cy="50" r="32" fill="#fff"/>
    <path d="M50 26c-8 9-14 16-14 25a14 14 0 0028 0c0-9-6-16-14-25Z" fill="#ea580c"/>
    <circle cx="50" cy="53" r="6" fill="#fef08a"/>
  </svg>`,

  sprinkler: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0369a1"/>
    <rect x="40" y="14" width="20" height="14" rx="3" fill="#fff"/>
    <line x1="50" y1="28" x2="50" y2="44" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
    <circle cx="50" cy="38" r="6" fill="#ef4444"/>
    <path d="M26 48h48l-24 20Z" fill="#fff"/>
    <line x1="22" y1="68" x2="14" y2="86" stroke="#7dd3fc" stroke-width="5" stroke-linecap="round"/>
    <line x1="50" y1="72" x2="50" y2="90" stroke="#7dd3fc" stroke-width="5" stroke-linecap="round"/>
    <line x1="78" y1="68" x2="86" y2="86" stroke="#7dd3fc" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  exitlight: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#15803d"/>
    <rect x="10" y="22" width="80" height="56" rx="8" fill="#166534" stroke="#4ade80" stroke-width="3"/>
    <!-- Running person -->
    <circle cx="36" cy="38" r="6" fill="#fff"/>
    <path d="M36 44l-6 12h14M36 44l4 6 6-4" stroke="#fff" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <line x1="30" y1="56" x2="26" y2="68" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>
    <line x1="42" y1="56" x2="46" y2="68" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>
    <!-- Arrow -->
    <line x1="58" y1="50" x2="84" y2="50" stroke="#4ade80" stroke-width="6" stroke-linecap="round"/>
    <path d="M76 42l12 8-12 8" stroke="#4ade80" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <!-- Door -->
    <rect x="82" y="36" width="6" height="28" rx="2" fill="#fff"/>
  </svg>`,

  exitdoor: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#16a34a"/>
    <rect x="20" y="14" width="60" height="72" rx="6" fill="#fff"/>
    <path d="M42 50l20-16v32Z" fill="#16a34a"/>
    <circle cx="70" cy="50" r="3.5" fill="#16a34a"/>
  </svg>`,

  emlight: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#d97706"/>
    <rect x="16" y="44" width="68" height="36" rx="8" fill="#fff"/>
    <circle cx="32" cy="30" r="14" fill="#fff"/>
    <circle cx="32" cy="30" r="9" fill="#facc15"/>
    <circle cx="68" cy="30" r="14" fill="#fff"/>
    <circle cx="68" cy="30" r="9" fill="#facc15"/>
    <circle cx="50" cy="62" r="4" fill="#16a34a"/>
  </svg>`,

  firecabinet: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#991b1b"/>
    <rect x="16" y="16" width="68" height="68" rx="8" fill="#fff"/>
    <rect x="22" y="22" width="56" height="56" rx="4" fill="#dc2626"/>
    <!-- Hose reel -->
    <circle cx="50" cy="50" r="18" fill="none" stroke="#fff" stroke-width="4.5"/>
    <circle cx="50" cy="50" r="9" fill="#fff"/>
    <circle cx="50" cy="50" r="4" fill="#dc2626"/>
    <!-- Pipe going right -->
    <line x1="68" y1="50" x2="80" y2="50" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <path d="M78 44l8 6-8 6" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`,

  hydrant: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#991b1b"/>
    <rect x="36" y="32" width="28" height="48" rx="4" fill="#fff"/>
    <line x1="24" y1="44" x2="76" y2="44" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
    <line x1="24" y1="60" x2="76" y2="60" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
    <circle cx="50" cy="22" r="12" fill="#fff"/>
    <circle cx="50" cy="22" r="6" fill="#991b1b"/>
    <rect x="38" y="80" width="24" height="8" rx="3" fill="#fff"/>
  </svg>`,

  siamese: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#b91c1c"/>
    <line x1="50" y1="82" x2="50" y2="54" stroke="#fff" stroke-width="12" stroke-linecap="round"/>
    <path d="M30 32l20 22 20-22" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <circle cx="30" cy="32" r="10" fill="#facc15" stroke="#fff" stroke-width="3"/>
    <circle cx="70" cy="32" r="10" fill="#facc15" stroke="#fff" stroke-width="3"/>
  </svg>`,

  foamtank: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0f766e"/>
    <rect x="20" y="18" width="60" height="64" rx="14" fill="#fff"/>
    <!-- Tank stripes and FOAM symbol: wave lines -->
    <path d="M30 42 Q37 36 44 42 Q51 48 58 42 Q65 36 72 42" stroke="#0f766e" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <path d="M30 54 Q37 48 44 54 Q51 60 58 54 Q65 48 72 54" stroke="#0f766e" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <path d="M30 66 Q37 60 44 66 Q51 72 58 66 Q65 60 72 66" stroke="#0f766e" stroke-width="4.5" fill="none" stroke-linecap="round"/>
    <rect x="28" y="20" width="44" height="14" rx="6" fill="#facc15"/>
    <!-- F shape via rectangles -->
    <rect x="33" y="23" width="6" height="8" fill="#0f766e"/>
    <rect x="33" y="23" width="14" height="3" fill="#0f766e"/>
    <rect x="33" y="27" width="10" height="2" fill="#0f766e"/>
  </svg>`,

  fapanel: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#991b1b"/>
    <rect x="16" y="16" width="68" height="68" rx="8" fill="#fff"/>
    <rect x="24" y="24" width="52" height="26" rx="4" fill="#1e293b"/>
    <!-- Signal bars / indicator -->
    <rect x="30" y="38" width="6" height="8" rx="1" fill="#22c55e"/>
    <rect x="40" y="33" width="6" height="13" rx="1" fill="#22c55e"/>
    <rect x="50" y="28" width="6" height="18" rx="1" fill="#facc15"/>
    <rect x="60" y="33" width="6" height="13" rx="1" fill="#dc2626"/>
    <!-- LED dots below panel -->
    <circle cx="30" cy="64" r="5" fill="#16a34a"/>
    <circle cx="43" cy="64" r="5" fill="#facc15"/>
    <circle cx="56" cy="64" r="5" fill="#dc2626"/>
    <circle cx="69" cy="64" r="5" fill="#94a3b8"/>
  </svg>`,

  fireroll_door: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#b91c1c"/>
    <rect x="18" y="20" width="64" height="60" rx="4" fill="#fff"/>
    <line x1="22" y1="32" x2="78" y2="32" stroke="#b91c1c" stroke-width="4"/>
    <line x1="22" y1="44" x2="78" y2="44" stroke="#b91c1c" stroke-width="4"/>
    <line x1="22" y1="56" x2="78" y2="56" stroke="#b91c1c" stroke-width="4"/>
    <line x1="22" y1="68" x2="78" y2="68" stroke="#b91c1c" stroke-width="4"/>
    <line x1="50" y1="36" x2="50" y2="66" stroke="#16a34a" stroke-width="5" stroke-linecap="round"/>
    <path d="M42 60l8 8 8-8" stroke="#16a34a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`,

  smoke_fan: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#475569"/>
    <circle cx="50" cy="50" r="32" fill="#fff"/>
    <circle cx="50" cy="50" r="10" fill="#1e293b"/>
    <path d="M50 40c0-12 12-16 16-16s4 12-8 16Z" fill="#0284c7"/>
    <path d="M60 50c12 0 16 12 16 16s-12 4-16-8Z" fill="#0284c7"/>
    <path d="M50 60c0 12-12 16-16 16s-4-12 8-16Z" fill="#0284c7"/>
    <path d="M40 50c-12 0-16-12-16-16s12-4 16 8Z" fill="#0284c7"/>
  </svg>`,

  fire_ladder: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#16a34a"/>
    <line x1="34" y1="14" x2="34" y2="86" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
    <line x1="66" y1="14" x2="66" y2="86" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
    <line x1="34" y1="28" x2="66" y2="28" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <line x1="34" y1="44" x2="66" y2="44" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <line x1="34" y1="60" x2="66" y2="60" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <line x1="34" y1="76" x2="66" y2="76" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  /* ===== NHÓM 3: BÌNH CHỮA CHÁY (10 Loại) ===== */

  ext_co2_5: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#b91c1c"/>
    <!-- CO2 tank body (black body) -->
    <rect x="34" y="28" width="32" height="52" rx="12" fill="#fff"/>
    <rect x="36" y="30" width="28" height="48" rx="10" fill="#1e293b"/>
    <!-- Valve head -->
    <rect x="42" y="18" width="16" height="10" rx="4" fill="#fff"/>
    <!-- Horn/diffuser -->
    <path d="M58 22l18 10-12 8" fill="#1e293b" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>
    <!-- CO2 label: two circles for molecule (O-C-O) -->
    <circle cx="38" cy="54" r="5" fill="#7dd3fc"/>
    <circle cx="50" cy="54" r="5" fill="#bfdbfe"/>
    <circle cx="62" cy="54" r="5" fill="#7dd3fc"/>
    <line x1="43" y1="54" x2="45" y2="54" stroke="#fff" stroke-width="2"/>
    <line x1="55" y1="54" x2="57" y2="54" stroke="#fff" stroke-width="2"/>
    <!-- 5kg indicator: 5 dots -->
    <circle cx="38" cy="66" r="3" fill="#facc15"/>
    <circle cx="46" cy="66" r="3" fill="#facc15"/>
    <circle cx="54" cy="66" r="3" fill="#facc15"/>
    <circle cx="62" cy="66" r="3" fill="#facc15"/>
    <path d="M66 66l4-4v8" stroke="#facc15" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`,

  ext_abc_8: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#dc2626"/>
    <!-- ABC powder tank body -->
    <rect x="32" y="26" width="36" height="54" rx="12" fill="#fff"/>
    <rect x="34" y="28" width="32" height="50" rx="10" fill="#b91c1c"/>
    <!-- Valve head -->
    <rect x="40" y="16" width="20" height="10" rx="4" fill="#fff"/>
    <!-- Pressure gauge -->
    <circle cx="68" cy="22" r="6" fill="#facc15" stroke="#fff" stroke-width="2"/>
    <line x1="68" y1="18" x2="68" y2="22" stroke="#1e293b" stroke-width="2" stroke-linecap="round"/>
    <!-- Powder label: 3 horizontal bands  -->
    <rect x="38" y="44" width="24" height="6" rx="2" fill="#facc15"/>
    <rect x="38" y="54" width="24" height="6" rx="2" fill="#facc15" opacity="0.7"/>
    <rect x="38" y="64" width="24" height="6" rx="2" fill="#facc15" opacity="0.4"/>
    <!-- 8kg indicator: 8-shape = two squares stacked -->
    <rect x="42" y="44" width="6" height="5" rx="1.5" fill="#fff" opacity="0.5"/>
    <rect x="42" y="51" width="6" height="5" rx="1.5" fill="#fff" opacity="0.5"/>
  </svg>`,

  ext_abc_35: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#7f1d1d"/>
    <!-- Wheeled base -->
    <circle cx="28" cy="78" r="11" fill="#1e293b" stroke="#fff" stroke-width="3"/>
    <circle cx="72" cy="78" r="11" fill="#1e293b" stroke="#fff" stroke-width="3"/>
    <line x1="28" y1="78" x2="72" y2="78" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
    <!-- Big tank body -->
    <rect x="30" y="16" width="40" height="58" rx="12" fill="#fff"/>
    <rect x="32" y="18" width="36" height="54" rx="10" fill="#7f1d1d"/>
    <!-- Valve -->
    <rect x="38" y="8" width="24" height="8" rx="4" fill="#fff"/>
    <!-- Powder bands (large = 35kg) -->
    <rect x="36" y="34" width="28" height="8" rx="2" fill="#facc15"/>
    <rect x="36" y="46" width="28" height="8" rx="2" fill="#facc15" opacity="0.7"/>
    <rect x="36" y="58" width="28" height="8" rx="2" fill="#facc15" opacity="0.4"/>
  </svg>`,

  ext_foam_9: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0f766e"/>
    <!-- Foam tank body -->
    <rect x="32" y="26" width="36" height="54" rx="12" fill="#fff"/>
    <rect x="34" y="28" width="32" height="50" rx="10" fill="#0f766e"/>
    <!-- Valve -->
    <rect x="40" y="16" width="20" height="10" rx="4" fill="#fff"/>
    <!-- Foam: bubble pattern (circles) -->
    <circle cx="41" cy="50" r="6" fill="#facc15" opacity="0.9"/>
    <circle cx="55" cy="46" r="6" fill="#facc15" opacity="0.9"/>
    <circle cx="60" cy="58" r="6" fill="#facc15" opacity="0.9"/>
    <circle cx="42" cy="62" r="5" fill="#facc15" opacity="0.7"/>
    <circle cx="52" cy="58" r="4" fill="#facc15" opacity="0.8"/>
    <!-- 9L indicator: 9-dot grid (3x3) -->
    <circle cx="41" cy="74" r="2.5" fill="#fff"/>
    <circle cx="50" cy="74" r="2.5" fill="#fff"/>
    <circle cx="59" cy="74" r="2.5" fill="#fff"/>
  </svg>`,

  ext_clean_gas: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#4f46e5"/>
    <!-- Clean gas cylinder: silver body -->
    <rect x="32" y="26" width="36" height="54" rx="12" fill="#fff"/>
    <rect x="34" y="28" width="32" height="50" rx="10" fill="#4338ca"/>
    <!-- Valve -->
    <rect x="40" y="16" width="20" height="10" rx="4" fill="#fff"/>
    <!-- Clean symbol: sparkle/star -->
    <path d="M50 38l3 6 6 3-6 3-3 6-3-6-6-3 6-3Z" fill="#fff"/>
    <!-- Molecular dots pattern (clean = pure) -->
    <circle cx="40" cy="62" r="4" fill="#a5b4fc"/>
    <circle cx="50" cy="58" r="4" fill="#c7d2fe"/>
    <circle cx="60" cy="62" r="4" fill="#a5b4fc"/>
    <circle cx="50" cy="70" r="4" fill="#c7d2fe"/>
    <line x1="44" y1="62" x2="46" y2="60" stroke="#fff" stroke-width="1.5"/>
    <line x1="54" y1="60" x2="56" y2="62" stroke="#fff" stroke-width="1.5"/>
    <line x1="54" y1="68" x2="56" y2="66" stroke="#fff" stroke-width="1.5"/>
    <line x1="44" y1="66" x2="46" y2="68" stroke="#fff" stroke-width="1.5"/>
  </svg>`,

  ext_water_mist: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#0284c7"/>
    <!-- Water body -->
    <rect x="32" y="26" width="36" height="54" rx="12" fill="#fff"/>
    <rect x="34" y="28" width="32" height="50" rx="10" fill="#0369a1"/>
    <!-- Valve -->
    <rect x="40" y="16" width="20" height="10" rx="4" fill="#fff"/>
    <!-- Water droplets spraying out -->
    <path d="M50 44c0-6 5-10 5-10s5 4 5 10a5 5 0 01-10 0Z" fill="#7dd3fc"/>
    <circle cx="38" cy="56" r="4" fill="#7dd3fc"/>
    <circle cx="62" cy="56" r="4" fill="#7dd3fc"/>
    <circle cx="44" cy="68" r="3.5" fill="#bae6fd"/>
    <circle cx="56" cy="68" r="3.5" fill="#bae6fd"/>
    <circle cx="50" cy="74" r="3" fill="#e0f2fe"/>
  </svg>`,

  ext_pair_abc: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#ef4444"/>
    <!-- Left tank -->
    <rect x="12" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="14" y="30" width="30" height="48" rx="8" fill="#dc2626"/>
    <rect x="18" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <rect x="14" y="50" width="30" height="6" rx="2" fill="#facc15"/>
    <rect x="14" y="60" width="30" height="6" rx="2" fill="#facc15" opacity="0.6"/>
    <!-- Right tank -->
    <rect x="54" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="56" y="30" width="30" height="48" rx="8" fill="#dc2626"/>
    <rect x="64" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <rect x="56" y="50" width="30" height="6" rx="2" fill="#facc15"/>
    <rect x="56" y="60" width="30" height="6" rx="2" fill="#facc15" opacity="0.6"/>
    <line x1="10" y1="82" x2="90" y2="82" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  ext_pair_co2: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#be123c"/>
    <!-- Left CO2 (dark body) -->
    <rect x="12" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="14" y="30" width="30" height="48" rx="8" fill="#1e293b"/>
    <rect x="18" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <circle cx="22" cy="54" r="5" fill="#7dd3fc"/>
    <circle cx="29" cy="54" r="5" fill="#bfdbfe"/>
    <circle cx="36" cy="54" r="5" fill="#7dd3fc"/>
    <!-- Right CO2 -->
    <rect x="54" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="56" y="30" width="30" height="48" rx="8" fill="#1e293b"/>
    <rect x="64" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <circle cx="64" cy="54" r="5" fill="#7dd3fc"/>
    <circle cx="71" cy="54" r="5" fill="#bfdbfe"/>
    <circle cx="78" cy="54" r="5" fill="#7dd3fc"/>
    <line x1="10" y1="82" x2="90" y2="82" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  ext_pair_mix: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#e11d48"/>
    <!-- Left ABC (red) -->
    <rect x="12" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="14" y="30" width="30" height="48" rx="8" fill="#dc2626"/>
    <rect x="18" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <rect x="14" y="50" width="30" height="6" rx="2" fill="#facc15"/>
    <!-- Right CO2 (dark) -->
    <rect x="54" y="28" width="34" height="52" rx="10" fill="#fff"/>
    <rect x="56" y="30" width="30" height="48" rx="8" fill="#1e293b"/>
    <rect x="64" y="18" width="16" height="10" rx="3" fill="#fff"/>
    <circle cx="64" cy="54" r="5" fill="#7dd3fc"/>
    <circle cx="71" cy="54" r="5" fill="#bfdbfe"/>
    <circle cx="78" cy="54" r="5" fill="#7dd3fc"/>
    <line x1="10" y1="82" x2="90" y2="82" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
  </svg>`,

  ext_trio: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#991b1b"/>
    <!-- ABC left -->
    <rect x="6" y="30" width="26" height="50" rx="7" fill="#fff"/>
    <rect x="8" y="32" width="22" height="46" rx="6" fill="#dc2626"/>
    <rect x="11" y="20" width="12" height="8" rx="3" fill="#fff"/>
    <rect x="8" y="50" width="22" height="5" rx="2" fill="#facc15"/>
    <!-- CO2 middle -->
    <rect x="37" y="30" width="26" height="50" rx="7" fill="#fff"/>
    <rect x="39" y="32" width="22" height="46" rx="6" fill="#1e293b"/>
    <rect x="42" y="20" width="12" height="8" rx="3" fill="#fff"/>
    <circle cx="45" cy="54" r="4" fill="#7dd3fc"/>
    <circle cx="50" cy="54" r="4" fill="#bfdbfe"/>
    <circle cx="55" cy="54" r="4" fill="#7dd3fc"/>
    <!-- FOAM right -->
    <rect x="68" y="30" width="26" height="50" rx="7" fill="#fff"/>
    <rect x="70" y="32" width="22" height="46" rx="6" fill="#0f766e"/>
    <rect x="73" y="20" width="12" height="8" rx="3" fill="#fff"/>
    <circle cx="76" cy="50" r="4" fill="#facc15"/>
    <circle cx="84" cy="50" r="4" fill="#facc15"/>
    <circle cx="76" cy="60" r="4" fill="#facc15" opacity="0.7"/>
    <circle cx="84" cy="60" r="4" fill="#facc15" opacity="0.7"/>
    <line x1="4" y1="82" x2="96" y2="82" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/>
  </svg>`,

  route: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="18" fill="#16a34a"/>
    <path d="M22 68c14-20 22-20 34-20h14" stroke="#fff" stroke-width="8" stroke-linecap="round" fill="none"/>
    <path d="M64 34l16 14-16 14" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>`
};

/* ===== BACKWARD COMPATIBILITY ALIASES ===== */
SVG_ICONS.smoke_detector  = SVG_ICONS.smoke;
SVG_ICONS.heat_detector   = SVG_ICONS.heat;
SVG_ICONS.alarmbell       = SVG_ICONS.firebell;
SVG_ICONS.facp            = SVG_ICONS.fapanel;
SVG_ICONS.ext_trio_mix    = SVG_ICONS.ext_trio;
SVG_ICONS.firecab         = SVG_ICONS.firecabinet;
SVG_ICONS.ext_co2         = SVG_ICONS.ext_co2_5;
SVG_ICONS.ext_abc         = SVG_ICONS.ext_abc_8;
SVG_ICONS.ext_foam        = SVG_ICONS.ext_foam_9;

/* ===== PUBLIC API ===== */

const TYPES = {
  // === NHÓM 1: THIẾT BỊ AN TOÀN & Y TẾ (14 Loại) ===
  shower: {
    prefix: 'V',
    name: 'Vòi tắm khẩn cấp',
    nameEn: 'Emergency Safety Shower',
    nameZh: '紧急冲淋器',
    color: '#059669',
    hint: 'Dùng xối rửa khi dính hóa chất toàn thân (15 phút)',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 15
  },
  eyewash: {
    prefix: 'RM',
    name: 'Bồn rửa mắt khẩn cấp',
    nameEn: 'Emergency Eyewash Station',
    nameZh: '紧急洗眼器',
    color: '#0284c7',
    hint: 'Bồn/bình rửa mắt khẩn cấp cố định hoặc di động',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 15
  },
  map: {
    prefix: 'BD',
    name: 'Sơ đồ thoát hiểm',
    nameEn: 'Evacuation Map / Plan',
    nameZh: '疏散平面图',
    color: '#4f46e5',
    hint: 'Bảng sơ đồ chỉ dẫn thoát hiểm treo tường',
    group: 'safety',
    markerClass: 'square'
  },
  assembly: {
    prefix: 'TK',
    name: 'Điểm tập kết an toàn',
    nameEn: 'Emergency Assembly Point',
    nameZh: '紧急集合点',
    color: '#15803d',
    hint: 'Vị trí tập trung sơ tán ngoài trời (Assembly Point)',
    group: 'safety',
    markerClass: 'square'
  },
  firstaid: {
    prefix: 'F',
    name: 'Túi / Tủ sơ cấp cứu',
    nameEn: 'First Aid Box / Kit',
    nameZh: '急救医药箱',
    color: '#16a34a',
    hint: 'Tủ thuốc và dụng cụ y tế sơ cấp cứu tại chỗ',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 25
  },
  rescue: {
    prefix: 'CN',
    name: 'Tủ dụng cụ CNCH',
    nameEn: 'Rescue Tool Station',
    nameZh: '应急救援装备柜',
    color: '#ea580c',
    hint: 'Kìm cộng lực, rìu PCCC, búa tạ, găng tay cách điện...',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 30
  },
  spillkit: {
    prefix: 'SK',
    name: 'Bộ ứng phó tràn hóa chất',
    nameEn: 'Chemical Spill Kit',
    nameZh: '化学品泄漏应急套件',
    color: '#d97706',
    hint: 'Cát, phao quây, tấm thấm dầu/hóa chất tràn đổ',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 20
  },
  loto: {
    prefix: 'LT',
    name: 'Trạm khóa an toàn LOTO',
    nameEn: 'LOTO Safety Station',
    nameZh: '上锁挂牌工作站',
    color: '#dc2626',
    hint: 'Khóa & thẻ treo cảnh báo cô lập năng lượng',
    group: 'safety',
    markerClass: 'square'
  },
  scba: {
    prefix: 'SCBA',
    name: 'Bình thở dưỡng khí SCBA',
    nameEn: 'SCBA Breathing Apparatus',
    nameZh: '正压式空气呼吸器',
    color: '#0284c7',
    hint: 'Thiết bị thở độc lập dùng trong khói độc/thiếu oxy',
    group: 'safety',
    markerClass: 'square'
  },
  stretcher: {
    prefix: 'ST',
    name: 'Cáng cứu thương',
    nameEn: 'Medical Stretcher',
    nameZh: '急救担架',
    color: '#0d9488',
    hint: 'Cáng cứu thương gấp gọn hoặc cố định',
    group: 'safety',
    markerClass: 'wide'
  },
  gasdetector: {
    prefix: 'GD',
    name: 'Đầu dò khí độc / dễ cháy',
    nameEn: 'Gas / Toxic Detector',
    nameZh: '可燃及有毒气体探测器',
    color: '#7c3aed',
    hint: 'Cảm biến giám sát rò rỉ khí gas/khí độc liên tục',
    group: 'safety',
    markerClass: 'square',
    defaultRadius: 10
  },
  estop: {
    prefix: 'ES',
    name: 'Nút dừng khẩn cấp E-Stop',
    nameEn: 'Emergency Stop Button',
    nameZh: '急停按钮',
    color: '#eab308',
    hint: 'Nút nhấn dừng khẩn cấp dây chuyền/thiết bị điện',
    group: 'safety',
    markerClass: 'square'
  },
  fireblanket: {
    prefix: 'CB',
    name: 'Chăn dập lửa sợi thủy tinh',
    nameEn: 'Fire Blanket',
    nameZh: '灭火毯',
    color: '#ea580c',
    hint: 'Chăn dập lửa dập cháy dầu mỡ hoặc trùm bảo vệ người',
    group: 'safety',
    markerClass: 'square'
  },
  ppe_station: {
    prefix: 'PPE',
    name: 'Trạm trang bị bảo hộ (PPE)',
    nameEn: 'PPE Safety Station',
    nameZh: '个人防护用品站',
    color: '#0284c7',
    hint: 'Mũ, kính, găng tay, ủng, áo phản quang...',
    group: 'safety',
    markerClass: 'square'
  },

  // === NHÓM 2: PHƯƠNG TIỆN & HỆ THỐNG PCCC (16 Loại) ===
  callpoint: {
    prefix: 'BAO',
    name: 'Nút ấn báo cháy khẩn cấp',
    nameEn: 'Manual Fire Call Point',
    nameZh: '手动火灾报警按钮',
    color: '#dc2626',
    hint: 'Nút nhấn đập kính / ấn báo cháy truyền về trung tâm',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 30
  },
  firebell: {
    prefix: 'BC',
    name: 'Chuông / Còi báo cháy',
    nameEn: 'Fire Alarm Bell / Sounder',
    nameZh: '火灾警铃/声光报警器',
    color: '#dc2626',
    hint: 'Chuông còi cảnh báo cháy phát thanh âm lượng cao',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 35
  },
  smoke: {
    prefix: 'BK',
    name: 'Đầu báo khói tự động',
    nameEn: 'Smoke Detector',
    nameZh: '感烟火灾探测器',
    color: '#334155',
    hint: 'Đầu báo khói quang điện gắn trần',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 7.5
  },
  heat: {
    prefix: 'BN',
    name: 'Đầu báo nhiệt tự động',
    nameEn: 'Heat Detector',
    nameZh: '感温火灾探测器',
    color: '#ea580c',
    hint: 'Đầu báo gia tăng/cố định nhiệt độ gắn trần',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 5
  },
  sprinkler: {
    prefix: 'SP',
    name: 'Đầu phun Sprinkler PCCC',
    nameEn: 'Fire Sprinkler Head',
    nameZh: '自动喷水灭火喷头',
    color: '#0369a1',
    hint: 'Đầu phun chữa cháy tự động bằng nước vách tường/trần',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 3.5
  },
  exitlight: {
    prefix: 'EXIT',
    name: 'Đèn chỉ dẫn EXIT',
    nameEn: 'Emergency EXIT Sign',
    nameZh: '安全出口指示灯',
    color: '#15803d',
    hint: 'Đèn LED chỉ hướng cửa thoát nạn sáng liên tục + pin lưu điện',
    group: 'fireequipment',
    markerClass: 'wide'
  },
  exitdoor: {
    prefix: 'CT',
    name: 'Cửa thoát nạn PCCC',
    nameEn: 'Emergency Exit Door',
    nameZh: '消防安全疏散门',
    color: '#16a34a',
    hint: 'Cửa chống cháy mở 1 chiều, thanh đẩy panic bar',
    group: 'fireequipment',
    markerClass: 'square'
  },
  emlight: {
    prefix: 'DK',
    name: 'Đèn chiếu sáng sự cố',
    nameEn: 'Emergency Backup Light',
    nameZh: '应急照明灯',
    color: '#d97706',
    hint: 'Đèn 2 mắt tự sáng khi mất điện lưới phục vụ thoát nạn',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 15
  },
  firecabinet: {
    prefix: 'TCC',
    name: 'Tủ họng nước chữa cháy',
    nameEn: 'Fire Hose Cabinet',
    nameZh: '室内消火栓箱',
    color: '#991b1b',
    hint: 'Tủ gồm cuộn vòi D50/D65, lăng phun, van góc',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 25
  },
  hydrant: {
    prefix: 'TRU',
    name: 'Trụ nước PCCC ngoài nhà',
    nameEn: 'Outdoor Fire Hydrant',
    nameZh: '室外消火栓',
    color: '#991b1b',
    hint: 'Trụ cứu hỏa 2 hoặc 3 cửa ngoài sân/đường nội bộ',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 75
  },
  siamese: {
    prefix: 'HT',
    name: 'Họng tiếp nước PCCC (2 chạc)',
    nameEn: 'Siamese Fire Department Connection',
    nameZh: '水泵接合器',
    color: '#b91c1c',
    hint: 'Họng tiếp nước từ xe chữa cháy D65 vào đường ống tòa nhà',
    group: 'fireequipment',
    markerClass: 'square'
  },
  foamtank: {
    prefix: 'FOAM',
    name: 'Bình / Bồn Foam chữa cháy',
    nameEn: 'Foam System Tank',
    nameZh: '泡沫灭火系统储罐',
    color: '#0f766e',
    hint: 'Hệ thống bọt Foam dập đám cháy xăng dầu, hóa chất',
    group: 'fireequipment',
    markerClass: 'square',
    defaultRadius: 30
  },
  fapanel: {
    prefix: 'FACP',
    name: 'Tủ trung tâm báo cháy',
    nameEn: 'Fire Alarm Control Panel (FACP)',
    nameZh: '火灾报警控制器',
    color: '#991b1b',
    hint: 'Tủ trung tâm điều khiển báo cháy tự động',
    group: 'fireequipment',
    markerClass: 'square'
  },
  fireroll_door: {
    prefix: 'CC',
    name: 'Cửa cuốn ngăn cháy PCCC',
    nameEn: 'Fire Rolling Shutter',
    nameZh: '防火卷帘门',
    color: '#b91c1c',
    hint: 'Cửa cuốn ngăn cháy tự động hạ khi báo động',
    group: 'fireequipment',
    markerClass: 'wide'
  },
  smoke_fan: {
    prefix: 'QHK',
    name: 'Quạt hút khói / Tăng áp',
    nameEn: 'Smoke Extraction Fan',
    nameZh: '排烟风机',
    color: '#475569',
    hint: 'Hệ thống quạt hút khói hành lang và tăng áp cầu thang',
    group: 'fireequipment',
    markerClass: 'square'
  },
  fire_ladder: {
    prefix: 'TL',
    name: 'Thang thoát hiểm ngoài nhà',
    nameEn: 'Emergency Fire Escape Ladder',
    nameZh: '室外消防疏散梯',
    color: '#16a34a',
    hint: 'Thang thép thoát nạn khẩn cấp ngoài nhà',
    group: 'fireequipment',
    markerClass: 'square'
  },

  // === NHÓM 3: BỐ TRÍ BÌNH CHỮA CHÁY (10 Loại) ===
  ext_co2_5: {
    prefix: 'C5',
    name: 'Bình CO₂ 5 kg (lẻ)',
    nameEn: 'CO2 Extinguisher 5kg',
    nameZh: '二氧化碳灭火器 5kg',
    color: '#b91c1c',
    hint: '1 bình khí CO₂ 5 kg dập cháy điện, thiết bị điện tử, phòng máy',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 15,
    units: { co2: 1 }
  },
  ext_abc_8: {
    prefix: 'A8',
    name: 'Bình Bột ABC 8 kg (lẻ)',
    nameEn: 'ABC Powder Extinguisher 8kg',
    nameZh: 'ABC干粉灭火器 8kg',
    color: '#dc2626',
    hint: '1 bình bột ABC 8 kg dập cháy chất rắn, lỏng, khí',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 20,
    units: { abc8: 1 }
  },
  ext_abc_35: {
    prefix: 'A35',
    name: 'Bình ABC 35 kg (xe đẩy)',
    nameEn: 'Wheeled ABC Extinguisher 35kg',
    nameZh: '推车式ABC干粉灭火器 35kg',
    color: '#7f1d1d',
    hint: '1 bình xe đẩy ABC 35 kg bảo vệ nhà xưởng rộng, kho hàng lớn',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 30,
    units: { abc35: 1 }
  },
  ext_foam_9: {
    prefix: 'F9',
    name: 'Bình Bọt Foam 9 lít',
    nameEn: 'Foam Extinguisher 9L',
    nameZh: '泡沫灭火器 9L',
    color: '#0f766e',
    hint: '1 bình bọt Foam 9L dập cháy xăng dầu, dung môi hóa chất hữu cơ',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 15,
    units: { foam9: 1 }
  },
  ext_clean_gas: {
    prefix: 'CG5',
    name: 'Bình Khí sạch FM-200 / Novec',
    nameEn: 'Clean Agent Extinguisher',
    nameZh: '洁净气体灭火器',
    color: '#4f46e5',
    hint: 'Bình khí sạch không cặn cho phòng IT, Server, Tủ điện',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 15,
    units: { clean_gas: 1 }
  },
  ext_water_mist: {
    prefix: 'W6',
    name: 'Bình Bọt sinh học / Gốc nước 6L',
    nameEn: 'Water Mist / Eco Foam 6L',
    nameZh: '水基型灭火器 6L',
    color: '#0284c7',
    hint: 'Bình bọt gốc nước sinh học an toàn dập cháy pin lithium & dầu mỡ',
    group: 'extinguisher',
    markerClass: 'round',
    defaultRadius: 15,
    units: { water6: 1 }
  },
  ext_pair_abc: {
    prefix: '2A',
    name: 'Cặp Bột ABC (2 × 8kg)',
    nameEn: 'Pair ABC Powder (2x8kg)',
    nameZh: '双具ABC干粉灭火器组 (2x8kg)',
    color: '#ef4444',
    hint: 'Cặp 2 bình bột ABC 8 kg đặt cạnh nhau',
    group: 'extinguisher',
    markerClass: 'wide',
    pair: true,
    defaultRadius: 20,
    units: { abc8: 2 }
  },
  ext_pair_co2: {
    prefix: '2C',
    name: 'Cặp CO₂ (2 × 5kg)',
    nameEn: 'Pair CO2 (2x5kg)',
    nameZh: '双具CO2灭火器组 (2x5kg)',
    color: '#be123c',
    hint: 'Cặp 2 bình CO₂ 5 kg đặt cạnh nhau',
    group: 'extinguisher',
    markerClass: 'wide',
    pair: true,
    defaultRadius: 15,
    units: { co2: 2 }
  },
  ext_pair_mix: {
    prefix: 'AC',
    name: 'Cặp phối hợp (ABC 8kg + CO₂ 5kg)',
    nameEn: 'Combo Pair (ABC 8kg + CO2 5kg)',
    nameZh: '组合式灭火器组 (ABC 8kg + CO2 5kg)',
    color: '#e11d48',
    hint: 'Bố trí 1 bình ABC 8kg + 1 bình CO₂ 5kg',
    group: 'extinguisher',
    markerClass: 'wide',
    pair: true,
    defaultRadius: 20,
    units: { abc8: 1, co2: 1 }
  },
  ext_trio: {
    prefix: '3X',
    name: 'Cụm 3 bình (ABC 8kg + CO₂ 5kg + Foam 9L)',
    nameEn: 'Trio Set (ABC 8kg + CO2 5kg + Foam 9L)',
    nameZh: '三具多功能灭火器站',
    color: '#991b1b',
    hint: 'Trạm PCCC toàn diện gồm 3 bình (ABC 8kg + CO2 5kg + Foam 9L)',
    group: 'extinguisher',
    markerClass: 'wide',
    pair: true,
    defaultRadius: 20,
    units: { abc8: 1, co2: 1, foam9: 1 }
  }
};

const UNIT_LABELS = {
  co2: { vi: 'CO₂ 5kg', en: '5kg CO2', zh: '5kg 二氧化碳' },
  abc8: { vi: 'Bột ABC 8kg', en: '8kg ABC Powder', zh: '8kg ABC干粉' },
  abc35: { vi: 'ABC 35kg (xe đẩy)', en: '35kg Wheeled ABC', zh: '35kg 推车式ABC' },
  foam9: { vi: 'Bọt Foam 9L', en: '9L Foam', zh: '9L 泡沫' },
  clean_gas: { vi: 'Khí sạch FM-200', en: 'Clean Gas FM-200', zh: '气体灭火剂' },
  water6: { vi: 'Bọt sinh học 6L', en: 'Eco Foam 6L', zh: '水基灭火剂 6L' }
};

const ROUTE_TYPES = {
  primary: {
    name: 'Tuyến thoát hiểm chính',
    color: '#16a34a',
    outline: '#ffffff',
    width: 6,
    animated: true
  },
  secondary: {
    name: 'Tuyến thoát hiểm phụ',
    color: '#eab308',
    outline: '#ffffff',
    width: 4,
    animated: false
  },
  fireaccess: {
    name: 'Lối cứu hỏa & CNCH',
    color: '#dc2626',
    outline: '#ffffff',
    width: 6,
    animated: true
  }
};

const ZONE_PRESETS = {
  hazard_high: {
    name: 'Khu vực Nguy hiểm cao / Cháy nổ',
    fill: 'rgba(239, 68, 68, 0.22)',
    border: '#dc2626',
    borderWidth: 2
  },
  chemical: {
    name: 'Khu vực Lưu trữ Hóa chất',
    fill: 'rgba(234, 88, 12, 0.22)',
    border: '#ea580c',
    borderWidth: 2
  },
  keep_clear: {
    name: 'Vùng cấm vật cản / Cửa thoát nạn',
    fill: 'rgba(234, 179, 8, 0.22)',
    border: '#ca8a04',
    borderWidth: 2
  },
  electrical: {
    name: 'Trạm biến áp / Phòng máy điện',
    fill: 'rgba(99, 102, 241, 0.22)',
    border: '#4f46e5',
    borderWidth: 2
  }
};


/**
 * HSE Safety Layout Planner PRO - Core Application Engine
 * Version 8.5 PRO
 * Designed by LUV - Nguyễn Chí Tình
 */

const APP_DESIGNER = 'Nguyễn Chí Tình';
const STORAGE_KEY = 'hse_safety_layout_planner_pro_v85';
const PREV_STORAGE_KEYS = [
  'hse_safety_layout_planner_multisite_v8',
  'hse_safety_layout_planner_multisite_v7'
];
const MAX_IMAGE_BYTES = 3500000;

const EMPTY_PLAN_IMAGE = "data:image/svg+xml;utf8," + encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">
  <rect width="1200" height="800" fill="#f8fafc"/>
  <defs>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="1200" height="800" fill="url(#grid)" />
  <rect x="200" y="150" width="800" height="500" rx="16" fill="#ffffff" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="8 8"/>
  <text x="600" y="380" font-family="Arial, sans-serif" font-size="24" font-weight="bold" fill="#64748b" text-anchor="middle">CHƯA CÓ BẢN VẼ MẶT BẰNG</text>
  <text x="600" y="420" font-family="Arial, sans-serif" font-size="16" fill="#94a3b8" text-anchor="middle">Bấm "Tải bản vẽ" hoặc Kéo - Thả file hình ảnh (PNG, JPG, WEBP, SVG) vào đây</text>
</svg>`);

function makePlan(name = 'Sơ đồ 1') {
  return {
    id: 'plan_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 6),
    name,
    image: '',
    imageName: '',
    markers: [],
    routes: [],
    zones: []
  };
}

let state = {
  version: 8.5,
  projectName: '',
  currentPlan: 'plan_1',
  planOrder: ['plan_1'],
  titleBlock: {
    company: '',
    author: 'Nguyễn Chí Tình',
    approver: '',
    scale: '1:100',
    sheet: 'HSE-01',
    rev: '01',
    date: new Date().toLocaleDateString('vi-VN')
  },
  settings: {
    opacity: 85,
    size: 38,
    contrast: 110,
    snap: false,
    gridLines: false,
    coverageRadius: false,
    animatedRoutes: true,
    theme: 'dark'
  },
  plans: {
    plan_1: makePlan('Sơ đồ 1')
  }
};

let activeTool = null;
let activeToolCategory = 'all';
let selectedId = null;
let selectedRouteId = null;
let selectedZoneId = null;
let draggingMarker = null;
let draggingVertex = null;
let isPanning = false;
let panStart = { x: 0, y: 0 };
let spacePressed = false;
let panModeActive = false;

let routeDraft = [];
let routeModeType = null;
let zoneDraft = [];
let zoneModeActive = false;

let transform = { scale: 1, x: 0, y: 0 };
let history = [];
let future = [];

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

function planIds() {
  return (state.planOrder || []).filter(id => state.plans && state.plans[id]);
}

function currentPlanData() {
  return state.plans[state.currentPlan] || state.plans[planIds()[0]];
}


  // Global Icon & Type Helper Functions
  window.getHseIconSvg = function(type) {
    if (window.HSE_SVG_ICONS && window.HSE_SVG_ICONS[type]) {
      return window.HSE_SVG_ICONS[type];
    }
    // Fallback: generic safety box
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
      <rect width="100" height="100" rx="18" fill="#ef4444"/>
      <circle cx="50" cy="50" r="28" fill="#fff"/>
      <text x="50" y="58" font-size="28" font-family="Arial" font-weight="bold" fill="#ef4444" text-anchor="middle">HSE</text>
    </svg>`;
  };

  window.calculateHseExtinguishers = function(markers = []) {
    const totals = { co2: 0, abc8: 0, abc35: 0, foam9: 0, clean_gas: 0, water6: 0, points: 0 };
    for (const m of markers) {
      const t = (window.HSE_TYPES && window.HSE_TYPES[m.type]);
      if (!t || t.group !== 'extinguisher') continue;
      totals.points++;
      for (const [k, v] of Object.entries(t.units || {})) {
        totals[k] = (totals[k] || 0) + v;
      }
    }
    totals.totalCylinders = totals.co2 + totals.abc8 + totals.abc35 + totals.foam9 + totals.clean_gas + totals.water6;
    return totals;
  };

  // Pre-configured Sample Equipment & Evacuation Plans for Plant A and Plant C
  window.HSE_SAMPLE_PLANS = {
    A: {
      markers: [
        { id: "m_a1", type: "ext_pair_mix", label: "AC-01", x: 0.125, y: 0.185, radius: 20, dept: "Cửa thoát hiểm Tây 1", note: "Bình ABC 8kg + CO2 5kg đạt chuẩn TCVN", status: "good" },
        { id: "m_a2", type: "firecabinet", label: "TCC-01", x: 0.125, y: 0.320, radius: 25, dept: "Vách tường Tây - Trục D", note: "Cuộn vòi D65 dài 20m + lăng phun", status: "good" },
        { id: "m_a3", type: "eyewash", label: "RM-01", x: 0.280, y: 0.185, radius: 15, dept: "Trạm pha trộn dung môi", note: "Kiểm tra áp lực nước hàng tuần", status: "good" },
        { id: "m_a4", type: "shower", label: "V-01", x: 0.280, y: 0.220, radius: 15, dept: "Kho hóa chất trung gian", note: "Vòi xối toàn thân kết hợp bồn rửa mắt", status: "good" },
        { id: "m_a5", type: "ext_abc_35", label: "A35-01", x: 0.450, y: 0.420, radius: 30, dept: "Khu vực kho nguyên liệu hạt nhựa", note: "Xe đẩy bột ABC 35kg cơ động cao", status: "good" },
        { id: "m_a6", type: "firstaid", label: "F-01", x: 0.510, y: 0.185, radius: 25, dept: "Văn phòng quản đốc Xưởng A", note: "Túi y tế loại B theo Thông tư 19/2016/TT-BYT", status: "good" },
        { id: "m_a7", type: "exitlight", label: "EX-01", x: 0.050, y: 0.485, radius: 15, dept: "Cửa thoát hiểm chính 01", note: "Đèn LED tự sạc pin lưu điện 3 giờ", status: "good" },
        { id: "m_a8", type: "exitlight", label: "EX-02", x: 0.950, y: 0.485, radius: 15, dept: "Cửa thoát hiểm chính 02", note: "Đèn LED tự sạc pin lưu điện 3 giờ", status: "good" },
        { id: "m_a9", type: "fapanel", label: "FACP-01", x: 0.540, y: 0.185, radius: 15, dept: "Phòng điều khiển trung tâm", note: "Tủ báo cháy địa chỉ 4 loop", status: "good" },
        { id: "m_a10", type: "spillkit", label: "SK-01", x: 0.220, y: 0.720, radius: 20, dept: "Khu vực bồn chứa dung môi", note: "Thùng 120L: phao quây, tấm thấm và găng tay chống axit", status: "good" }
      ],
      routes: [
        {
          id: "r_a1",
          type: "primary",
          label: "Lối thoát hiểm chính hướng Tây",
          points: [{ x: 0.480, y: 0.480 }, { x: 0.300, y: 0.480 }, { x: 0.050, y: 0.480 }],
          note: "Hành lang thoát nạn thông thoáng rộng 2.5m"
        },
        {
          id: "r_a2",
          type: "primary",
          label: "Lối thoát hiểm chính hướng Đông",
          points: [{ x: 0.520, y: 0.480 }, { x: 0.750, y: 0.480 }, { x: 0.950, y: 0.480 }],
          note: "Dẫn trực tiếp ra sân đường nội bộ nhà máy"
        }
      ],
      zones: [
        {
          id: "z_a1",
          name: "Khu vực Nguy hiểm - Lưu trữ Dung môi Dễ cháy",
          preset: "chemical",
          points: [{ x: 0.180, y: 0.150 }, { x: 0.360, y: 0.150 }, { x: 0.360, y: 0.340 }, { x: 0.180, y: 0.340 }],
          note: "Yêu cầu trang bị thiết bị chống nổ Ex-proof & bình dập lửa tự động"
        },
        {
          id: "z_a2",
          name: "Trạm Biến Áp & Tủ Điện Tổng Xưởng A",
          preset: "electrical",
          points: [{ x: 0.680, y: 0.150 }, { x: 0.880, y: 0.150 }, { x: 0.880, y: 0.320 }, { x: 0.680, y: 0.320 }],
          note: "Chỉ người có chứng chỉ an toàn điện mới được tiếp cận"
        }
      ]
    },
    C: {
      markers: [
        { id: "m_c1", type: "ext_pair_mix", label: "AC-01", x: 0.150, y: 0.200, radius: 20, dept: "Cửa số 1 Xưởng C", note: "Bình đạt chuẩn", status: "good" },
        { id: "m_c2", type: "firecabinet", label: "TCC-01", x: 0.150, y: 0.450, radius: 25, dept: "Vách tường Bắc", note: "Tủ PCCC vách tường", status: "good" },
        { id: "m_c3", type: "firstaid", label: "F-01", x: 0.500, y: 0.200, radius: 25, dept: "Bàn kỹ thuật", note: "Tủ y tế sơ cứu", status: "good" },
        { id: "m_c4", type: "exitlight", label: "EX-01", x: 0.080, y: 0.500, radius: 15, dept: "Cửa thoát hiểm", note: "Đèn chỉ hướng", status: "good" }
      ],
      routes: [
        {
          id: "r_c1",
          type: "primary",
          label: "Tuyến thoát hiểm Xưởng C",
          points: [{ x: 0.500, y: 0.500 }, { x: 0.080, y: 0.500 }],
          note: "Lối thoát ra sân tập kết"
        }
      ],
      zones: [
        {
          id: "z_c1",
          name: "Khu vực Kho Thành Phẩm",
          preset: "keep_clear",
          points: [{ x: 0.600, y: 0.200 }, { x: 0.900, y: 0.200 }, { x: 0.900, y: 0.800 }, { x: 0.600, y: 0.800 }],
          note: "Không xếp hàng chắn lối đi và vòi chữa cháy"
        }
      ]
    }
  };




  // Export to global window namespace
  window.HSE_SVG_ICONS = SVG_ICONS;
  window.HSE_TYPES = TYPES;
  window.HSE_ROUTE_TYPES = ROUTE_TYPES;
  window.HSE_ZONE_PRESETS = ZONE_PRESETS;

})(window);
