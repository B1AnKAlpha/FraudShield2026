function createIcon(body: string) {
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
}

export const icons = {
  menu: createIcon(
    '<path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" />',
  ),
  home: createIcon(
    '<path d="M4 10.5L12 4l8 6.5" /><path d="M6 10v9h12v-9" /><path d="M10 19v-5h4v5" />',
  ),
  monitor: createIcon(
    '<rect x="5" y="4" width="14" height="16" rx="2" /><path d="M8 8h8" /><path d="M8 12h8" /><path d="M8 16h5" />',
  ),
  alerts: createIcon(
    '<path d="M12 4a5 5 0 0 0-5 5v2.2l-1.3 2.6A1 1 0 0 0 6.6 15h10.8a1 1 0 0 0 .9-1.2L17 11.2V9a5 5 0 0 0-5-5Z" /><path d="M10 18a2 2 0 0 0 4 0" />',
  ),
  analysis: createIcon(
    '<path d="M6 18V10" /><path d="M12 18V6" /><path d="M18 18v-8" /><path d="M4 18h16" />',
  ),
  focus: createIcon(
    '<rect x="5" y="7" width="11" height="11" rx="2" /><path d="M10 10h9v9" /><path d="M13 13l6-6" />',
  ),
  logs: createIcon(
    '<path d="M7 4h7l4 4v12H7z" /><path d="M14 4v4h4" /><path d="M10 12h5" /><path d="M10 16h5" />',
  ),
  params: createIcon(
    '<path d="M7 5v14" /><path d="M17 5v14" /><path d="M4 9h6" /><path d="M14 15h6" /><circle cx="10" cy="9" r="2" /><circle cx="14" cy="15" r="2" />',
  ),
  account: createIcon(
    '<circle cx="12" cy="8" r="3.5" /><path d="M5.5 19a6.5 6.5 0 0 1 13 0" />',
  ),
  info: createIcon(
    '<circle cx="12" cy="12" r="8" /><path d="M12 11v5" /><path d="M12 8h.01" />',
  ),
  logout: createIcon(
    '<path d="M9 5H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h3" /><path d="M13 8l5 4-5 4" /><path d="M18 12H9" />',
  ),
  settings: createIcon(
    '<path d="M12 8.5A3.5 3.5 0 1 0 12 15.5A3.5 3.5 0 1 0 12 8.5Z" /><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1 1 0 0 1 0 1.4l-1.1 1.1a1 1 0 0 1-1.4 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1 1 0 0 1-1 1h-1.6a1 1 0 0 1-1-1v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a1 1 0 0 1-1.4 0l-1.1-1.1a1 1 0 0 1 0-1.4l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a1 1 0 0 1-1-1v-1.6a1 1 0 0 1 1-1h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a1 1 0 0 1 0-1.4l1.1-1.1a1 1 0 0 1 1.4 0l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a1 1 0 0 1 1-1h1.6a1 1 0 0 1 1 1v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a1 1 0 0 1 1.4 0l1.1 1.1a1 1 0 0 1 0 1.4l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a1 1 0 0 1 1 1v1.6a1 1 0 0 1-1 1h-.2a1 1 0 0 0-.9.6Z" />',
  ),
  theme: createIcon(
    '<path d="M12 3v3" /><path d="M12 18v3" /><path d="M4.9 4.9l2.1 2.1" /><path d="M17 17l2.1 2.1" /><path d="M3 12h3" /><path d="M18 12h3" /><path d="M4.9 19.1 7 17" /><path d="M17 7l2.1-2.1" /><circle cx="12" cy="12" r="4" />',
  ),
  update: createIcon(
    '<path d="M8 16a4 4 0 0 1 0-8 4.8 4.8 0 0 1 9.1 1.5A3.2 3.2 0 0 1 17 16H8Z" /><path d="M12 9v6" /><path d="M9.5 12.5 12 15l2.5-2.5" />',
  ),
} as const;
