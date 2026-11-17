/* Biblioteca própria de ícones SVG editoriais (linha fina 1.5px, sem dependências externas) */

const ICON_PATHS = {
  search: `<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8"/>`,
  user: `<path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="8" r="4"/>`,
  heart: `<path d="M12 20.4s-7.5-4.7-9.2-9.2A5.2 5.2 0 0 1 12 6.6a5.2 5.2 0 0 1 9.2 4.6c-1.7 4.5-9.2 9.2-9.2 9.2Z"/>`,
  "heart-filled": `<path fill="currentColor" d="M12 20.4s-7.5-4.7-9.2-9.2A5.2 5.2 0 0 1 12 6.6a5.2 5.2 0 0 1 9.2 4.6c-1.7 4.5-9.2 9.2-9.2 9.2Z"/>`,
  bag: `<path d="M6 8h12l1 12H5L6 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>`,
  sun: `<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4m11.4-11.4 1.4-1.4"/>`,
  moon: `<path d="M20.2 14.4A8.5 8.5 0 0 1 9.6 3.8a8.5 8.5 0 1 0 10.6 10.6Z"/>`,
  menu: `<path d="M4 7h16M4 12h16M4 17h16"/>`,
  close: `<path d="M18 6 6 18M6 6l12 12"/>`,
  "arrow-right": `<path d="M5 12h14m-6-6 6 6-6 6"/>`,
  "arrow-left": `<path d="M19 12H5m6-6-6 6 6 6"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  sliders: `<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="var(--st-surface)"/><circle cx="15" cy="12" r="2" fill="var(--st-surface)"/><circle cx="8" cy="18" r="2" fill="var(--st-surface)"/>`,
  eye: `<path d="M2 12s3.8-6 10-6 10 6 10 6-3.8 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/>`,
  edit: `<path d="M15.5 4.5 19.5 8.5 8 20H4v-4L15.5 4.5Z"/>`,
  trash: `<path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13"/>`,
  sparkles: `<path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>`,
  printer: `<path d="M7 8V4h10v4"/><rect x="4" y="8" width="16" height="8" rx="1.5"/><path d="M7 13h10v7H7v-7Z"/>`,
  layers: `<path d="m12 3 9 4.5-9 4.5-9-4.5L12 3Z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/>`,
  shield: `<path d="M12 3 4.5 6v6c0 5 3.3 8.1 7.5 9 4.2-.9 7.5-4 7.5-9V6L12 3Z"/>`,
  plus: `<path d="M12 5v14M5 12h14"/>`,
  minus: `<path d="M5 12h14"/>`,
  download: `<path d="M12 4v11m0 0-4-4m4 4 4-4"/><path d="M5 19h14"/>`,
  "zoom-in": `<circle cx="11" cy="11" r="7"/><path d="m20 20-3.8-3.8M11 8v6M8 11h6"/>`,
  book: `<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5v-12Z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20"/>`,
  lock: `<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>`,
  help: `<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 1c0 1.8-2.5 2-2.5 3.5"/><circle cx="12" cy="17" r="0.6" fill="currentColor"/>`,
  bell: `<path d="M6 15a6 6 0 0 1 12 0c0 2 1 3 1 3H5s1-1 1-3Z"/><path d="M10.5 20a1.5 1.5 0 0 0 3 0"/>`,
  mappin: `<path d="M12 21s-6-5.5-6-10.5a6 6 0 1 1 12 0C18 15.5 12 21 12 21Z"/><circle cx="12" cy="10.5" r="2"/>`,
  "file-text": `<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>`,
  "chevron-down": `<path d="m6 9 6 6 6-6"/>`,
  award: `<circle cx="12" cy="9" r="5"/><path d="m9 13.5-1 7 4-2 4 2-1-7"/>`,
};

export function icon(name, size = 16, extraClass = "") {
  const path = ICON_PATHS[name] || ICON_PATHS.sparkles;
  return `<svg class="eg-ico ${extraClass}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
}
