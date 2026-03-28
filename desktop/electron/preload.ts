import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('desktopAPI', {
  minimize: () => ipcRenderer.invoke('window:minimize'),
  close: () => ipcRenderer.invoke('window:close'),
  loadSettings: () => ipcRenderer.invoke('settings:load'),
  saveSettings: (payload: unknown) => ipcRenderer.invoke('settings:save', payload),
  loadSettingsStatus: () => ipcRenderer.invoke('settings:status'),
  pickDirectory: () => ipcRenderer.invoke('dialog:pickDirectory'),
  runArchive: (payload: { video: string; generateAi: boolean }) => ipcRenderer.invoke('archive:run', payload),
  openPath: (targetPath: string) => ipcRenderer.invoke('shell:openPath', targetPath),
  showItem: (targetPath: string) => ipcRenderer.invoke('shell:showItem', targetPath),
  openExternal: (targetUrl: string) => ipcRenderer.invoke('shell:openExternal', targetUrl),
  onArchiveLog: (callback: (message: string) => void) => {
    const handler = (_event: unknown, message: string) => callback(message)
    ipcRenderer.on('archive-log', handler)
    return () => ipcRenderer.removeListener('archive-log', handler)
  },
})
