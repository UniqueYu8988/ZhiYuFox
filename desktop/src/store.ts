import { create } from 'zustand'

type RuntimeSettings = {
  sessdata: string
  output_dir: string
  minimax_api_key: string
  minimax_model: string
}

type RunResult = {
  videoTitle: string
  publishDate: string
  outputDir: string
  markdownPath: string
}

type SettingsStatus = {
  bilibili: {
    configured: boolean
    valid: boolean
    accountName: string
    accountId: string
    message: string
  }
  minimax: {
    configured: boolean
    valid: boolean
    model: string
    message: string
  }
}

type AppState = {
  videoInput: string
  generateAi: boolean
  logs: string[]
  status: string
  running: boolean
  settingsOpen: boolean
  settingsLoaded: boolean
  settings: RuntimeSettings
  settingsStatus: SettingsStatus
  result: RunResult | null
  setVideoInput: (value: string) => void
  setGenerateAi: (value: boolean) => void
  setSettingsOpen: (value: boolean) => void
  setSettingsLoaded: (value: boolean) => void
  setSettings: (value: RuntimeSettings) => void
  setSettingsStatus: (value: SettingsStatus) => void
  appendLog: (value: string) => void
  clearLogs: () => void
  setStatus: (value: string) => void
  setRunning: (value: boolean) => void
  setResult: (value: RunResult | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  videoInput: '',
  generateAi: true,
  logs: [],
  status: '等待输入',
  running: false,
  settingsOpen: false,
  settingsLoaded: false,
  settings: {
    sessdata: '',
    output_dir: '',
    minimax_api_key: '',
    minimax_model: 'MiniMax-M2.7',
  },
  settingsStatus: {
    bilibili: {
      configured: false,
      valid: false,
      accountName: '',
      accountId: '',
      message: '未配置 SESSDATA',
    },
    minimax: {
      configured: false,
      valid: false,
      model: 'MiniMax-M2.7',
      message: '未配置 API Key',
    },
  },
  result: null,
  setVideoInput: (value) => set({ videoInput: value }),
  setGenerateAi: (value) => set({ generateAi: value }),
  setSettingsOpen: (value) => set({ settingsOpen: value }),
  setSettingsLoaded: (value) => set({ settingsLoaded: value }),
  setSettings: (value) => set({ settings: value }),
  setSettingsStatus: (value) => set({ settingsStatus: value }),
  appendLog: (value) =>
    set((state) => ({
      logs: [...state.logs, ...value.split(/\r?\n/).filter(Boolean)],
    })),
  clearLogs: () => set({ logs: [] }),
  setStatus: (value) => set({ status: value }),
  setRunning: (value) => set({ running: value }),
  setResult: (value) => set({ result: value }),
}))
