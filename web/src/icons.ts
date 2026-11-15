const PATHS = {
  out: '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
  in: '<path d="M17 7 7 17"/><path d="M16 17H7V8"/>',
  self: '<circle cx="12" cy="12" r="3.5"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
  person: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c1.2-3.6 3.8-5.5 7-5.5s5.8 1.9 7 5.5"/>',
  shield: '<path d="M12 3 5 6v5c0 4.4 3 8.3 7 10 4-1.7 7-5.6 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  shieldOff: '<path d="M12 3 5 6v5c0 4.4 3 8.3 7 10 4-1.7 7-5.6 7-10V6l-7-3Z"/><path d="m9.5 9.5 5 5M14.5 9.5l-5 5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  cross: '<path d="M6 6l12 12M18 6 6 18"/>',
  ask: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.8"/><path d="M12 17.2v.1"/>',
  open: '<path d="M14 5h5v5"/><path d="M19 5 11 13"/><path d="M18 14v5H5V6h5"/>',
  reset: '<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.6"/><path d="M4 4v4.6h4.6"/>',
  send: '<path d="M4 12 20 4l-5 16-3.5-6.5L4 12Z"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="1.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  alert: '<path d="M12 4 3 19.5h18L12 4Z"/><path d="M12 10v4.5"/><path d="M12 17.2v.1"/>',
  down: '<path d="M12 5v14"/><path d="m6 13 6 6 6-6"/>',
  bargain: '<path d="M4 8h12l-3-3"/><path d="M20 16H8l3 3"/>',
} as const;

export type IconName = keyof typeof PATHS;

export function icon(name: IconName, label?: string): string {
  const a11y = label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"';
  return `<svg class="ic" viewBox="0 0 24 24" ${a11y} fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${PATHS[name]}</svg>`;
}
