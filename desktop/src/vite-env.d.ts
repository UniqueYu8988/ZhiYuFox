/// <reference types="vite/client" />

type RuntimeSettings = {
  sessdata: string
  output_dir: string
  minimax_api_key: string
  minimax_model: string
}

type ArchiveRunResult = {
  videoTitle: string
  publishDate: string
  outputDir: string
  markdownPath: string
  fileGenerated: boolean
  hasSubtitles: boolean
  subtitleGroupCount: number
  subtitleEntryCount: number
  pageCount: number
  pagesWithSubtitles: number
  missingSubtitlePages: string[]
  aiSkippedReason: string
  resultNote: string
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

interface Window {
  desktopAPI: {
    minimize: () => Promise<void>
    close: () => Promise<void>
    loadSettings: () => Promise<RuntimeSettings>
    saveSettings: (payload: RuntimeSettings) => Promise<RuntimeSettings>
    loadSettingsStatus: () => Promise<SettingsStatus>
    pickDirectory: () => Promise<string | null>
    runArchive: (payload: { video: string; generateAi: boolean }) => Promise<ArchiveRunResult>
    openPath: (targetPath: string) => Promise<void>
    showItem: (targetPath: string) => Promise<void>
    openExternal: (targetUrl: string) => Promise<void>
    onArchiveLog: (callback: (message: string) => void) => () => void
  }
}
