/**
 * Pegasus Phantom Menace - Electron preload.
 *
 * Exposes a minimal, context-isolated API to the renderer. No Node APIs leak
 * into the web page; everything goes through ipcRenderer.invoke.
 */
const { contextBridge, ipcRenderer } = require('electron');

const api = {
  /** Backend URL the renderer should use (Flask host:port). */
  getBackendUrl: () => ipcRenderer.invoke('backend:url'),

  /** Backend lifecycle. */
  startBackend: () => ipcRenderer.invoke('backend:start'),
  stopBackend: () => ipcRenderer.invoke('backend:stop'),

  /** Windows auto-start toggle. */
  getAutoStart: () => ipcRenderer.invoke('autostart:get'),
  setAutoStart: (enable) => ipcRenderer.invoke('autostart:set', !!enable),

  /** App info. */
  getVersion: () => ipcRenderer.invoke('app:version'),

  /** External links (never navigate the app window away). */
  openExternal: (url) => ipcRenderer.invoke('shell:open-external', url),

  /** Platform helpers. */
  platform: process.platform,
  isDev: process.argv.includes('--dev'),
};

contextBridge.exposeInMainWorld('pegasus', api);
