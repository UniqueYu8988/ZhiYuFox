import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'

const APP_NAME = '知语狸'
const APP_ID = 'Zhiyuli'

app.name = APP_NAME
app.setAppUserModelId(APP_ID)

let mainWindow: BrowserWindow | null = null

function resolveDevProjectRoot() {
  const searchRoots = [
    path.dirname(process.execPath),
    process.cwd(),
    __dirname,
  ].filter(Boolean)

  for (const root of searchRoots) {
    for (let depth = 0; depth <= 6; depth += 1) {
      const candidate = path.resolve(root, ...Array(depth).fill('..'))
      if (fs.existsSync(path.join(candidate, 'src', 'main.py'))) {
        return candidate
      }
    }
  }

  const desktopRootFallback = path.resolve(__dirname, '..')
  return path.resolve(desktopRootFallback, '..')
}

function resolvePortableExecutableDir() {
  return process.env.PORTABLE_EXECUTABLE_DIR || path.dirname(process.execPath)
}

function findExistingDataRoot() {
  const searchRoots = [
    resolvePortableExecutableDir(),
    path.dirname(process.execPath),
    process.cwd(),
  ].filter(Boolean)

  for (const root of searchRoots) {
    for (let depth = 0; depth <= 6; depth += 1) {
      const candidate = path.resolve(root, ...Array(depth).fill('..'))
      if (fs.existsSync(path.join(candidate, '.biliarchive.local.json'))) {
        return candidate
      }
    }
  }

  return null
}

const devProjectRoot = resolveDevProjectRoot()
const dataRoot = app.isPackaged ? (findExistingDataRoot() || resolvePortableExecutableDir()) : devProjectRoot
const backendRoot = app.isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(devProjectRoot, 'src')
const pythonEntryPath = path.join(backendRoot, 'main.py')
const settingsPath = path.join(dataRoot, '.biliarchive.local.json')
const windowStatePath = path.join(dataRoot, '.biliarchive.window.json')
const runtimeLogPath = path.join(dataRoot, '.zhiyuli-runtime.log')
const iconPath = app.isPackaged
  ? path.join(process.resourcesPath, 'assets', 'app_icon.ico')
  : path.join(devProjectRoot, 'assets', 'app_icon.ico')

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
  fileGenerated: boolean
  hasSubtitles: boolean
  subtitleGroupCount: number
  subtitleEntryCount: number
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

function loadWindowState() {
  try {
    if (fs.existsSync(windowStatePath)) {
      const state = JSON.parse(fs.readFileSync(windowStatePath, 'utf-8'))
      return {
        width: Math.min(Math.max(Number(state.width) || 388, 388), 460),
        height: Math.min(Math.max(Number(state.height) || 680, 680), 820),
        x: typeof state.x === 'number' ? state.x : undefined,
        y: typeof state.y === 'number' ? state.y : undefined,
      }
    }
  } catch {
    // ignore
  }
  return { width: 388, height: 680 }
}

function saveWindowState() {
  if (!mainWindow) return
  try {
    const bounds = mainWindow.getBounds()
    fs.writeFileSync(windowStatePath, JSON.stringify(bounds, null, 2))
  } catch {
    // ignore
  }
}

function defaultSettings(): RuntimeSettings {
  return {
    sessdata: '',
    output_dir: path.join(dataRoot, 'output'),
    minimax_api_key: '',
    minimax_model: 'MiniMax-M2.7',
  }
}

function loadSettings(): RuntimeSettings {
  try {
    if (!fs.existsSync(settingsPath)) return defaultSettings()
    const raw = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
    return {
      sessdata: String(raw.sessdata ?? ''),
      output_dir: String(raw.output_dir ?? path.join(dataRoot, 'output')),
      minimax_api_key: String(raw.minimax_api_key ?? ''),
      minimax_model: String(raw.minimax_model ?? 'MiniMax-M2.7'),
    }
  } catch {
    return defaultSettings()
  }
}

function saveSettings(next: RuntimeSettings) {
  fs.writeFileSync(settingsPath, JSON.stringify(next, null, 2), 'utf-8')
  return next
}

function appendRuntimeLog(message: string) {
  try {
    const line = `[${new Date().toISOString()}] ${message}\n`
    fs.appendFileSync(runtimeLogPath, line, 'utf-8')
  } catch {
    // ignore
  }
}

function emitArchiveLog(message: string) {
  appendRuntimeLog(message)
  mainWindow?.webContents.send('archive-log', message.endsWith('\n') ? message : `${message}\n`)
}

function findExecutableOnPath(names: string[]) {
  const pathEntries = (process.env.PATH || '').split(path.delimiter).filter(Boolean)
  const pathExts = process.platform === 'win32'
    ? (process.env.PATHEXT || '.EXE;.CMD;.BAT').split(';')
    : ['']

  for (const entry of pathEntries) {
    for (const name of names) {
      const direct = path.join(entry, name)
      if (fs.existsSync(direct)) return direct
      for (const ext of pathExts) {
        const candidate = path.join(entry, name.endsWith(ext.toLowerCase()) ? name : `${name}${ext.toLowerCase()}`)
        if (fs.existsSync(candidate)) return candidate
      }
    }
  }

  return null
}

function resolvePythonCommand() {
  if (process.platform !== 'win32') {
    return { command: findExecutableOnPath(['python3', 'python']) || 'python3', prefixArgs: [] as string[] }
  }

  const localAppData = process.env.LOCALAPPDATA || path.join(process.env.USERPROFILE || '', 'AppData', 'Local')
  const commonCandidates = [
    findExecutableOnPath(['python.exe', 'python']),
    path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
    path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'),
    path.join(localAppData, 'Programs', 'Python', 'Python310', 'python.exe'),
  ].filter((value): value is string => typeof value === 'string' && value.length > 0)
   .filter((value) => fs.existsSync(value))

  if (commonCandidates[0]) {
    return { command: commonCandidates[0], prefixArgs: [] as string[] }
  }

  const pyLauncher = findExecutableOnPath(['py.exe', 'py'])
  if (pyLauncher) {
    return { command: pyLauncher, prefixArgs: ['-3'] }
  }

  return { command: 'python', prefixArgs: [] as string[] }
}

async function fetchSettingsStatus(settings: RuntimeSettings = loadSettings()): Promise<SettingsStatus> {
  const bilibili = {
    configured: Boolean(settings.sessdata.trim()),
    valid: false,
    accountName: '',
    accountId: '',
    message: '未配置 SESSDATA',
  }

  if (bilibili.configured) {
    try {
      const response = await fetch('https://api.bilibili.com/x/web-interface/nav', {
        headers: {
          Cookie: `SESSDATA=${settings.sessdata.trim()}`,
          Referer: 'https://www.bilibili.com',
          'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
      })
      const payload = await response.json()
      const data = payload?.data ?? {}
      if (payload?.code === 0 && data?.isLogin) {
        bilibili.valid = true
        bilibili.accountName = String(data.uname ?? '')
        bilibili.accountId = String(data.mid ?? '')
        bilibili.message = bilibili.accountName
          ? `已登录 ${bilibili.accountName}`
          : '已登录'
      } else {
        bilibili.message = '登录状态无效'
      }
    } catch {
      bilibili.message = '登录状态检测失败'
    }
  }

  const minimax = {
    configured: Boolean(settings.minimax_api_key.trim()),
    valid: false,
    model: settings.minimax_model || 'MiniMax-M2.7',
    message: '未配置 API Key',
  }

  if (minimax.configured) {
    try {
      const response = await fetch('https://api.minimaxi.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${settings.minimax_api_key.trim()}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: minimax.model,
          messages: [{ role: 'user', content: '请回复：ok' }],
          temperature: 0.1,
          max_tokens: 8,
        }),
      })

      if (response.ok) {
        const payload = await response.json()
        minimax.valid = Boolean(payload?.choices?.length)
        minimax.message = minimax.valid ? `已配置 ${minimax.model}` : '返回结果异常'
      } else if (response.status === 401) {
        minimax.message = 'API Key 无效'
      } else if (response.status === 403) {
        minimax.message = 'API Key 无权限'
      } else {
        minimax.message = `校验失败 · HTTP ${response.status}`
      }
    } catch {
      minimax.message = 'API 检测失败'
    }
  }

  return { bilibili, minimax }
}

function createWindow() {
  const state = loadWindowState()
  appendRuntimeLog(`createWindow dataRoot=${dataRoot} backendRoot=${backendRoot}`)

  mainWindow = new BrowserWindow({
    width: state.width ?? 388,
    height: state.height ?? 680,
    x: state.x,
    y: state.y,
    minWidth: 388,
    minHeight: 680,
    maxWidth: 460,
    maxHeight: 820,
    backgroundColor: '#00000000',
    titleBarStyle: 'hidden',
    titleBarOverlay: false,
    autoHideMenuBar: true,
    show: false,
    transparent: true,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('resize', saveWindowState)
  mainWindow.on('move', saveWindowState)
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

function runPythonArchive(video: string, generateAi: boolean): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const pythonCommand = resolvePythonCommand()
    const args = [...pythonCommand.prefixArgs, pythonEntryPath, video, '--result-json']
    if (!generateAi) args.push('--no-ai')
    emitArchiveLog(`启动归档任务：${video}`)
    appendRuntimeLog(`spawn command=${pythonCommand.command} args=${JSON.stringify(args)} cwd=${dataRoot}`)

    const child = spawn(pythonCommand.command, args, {
      cwd: dataRoot,
      windowsHide: true,
      env: {
        ...process.env,
        BILIARCHIVE_HOME: dataRoot,
        BILIARCHIVE_SETTINGS_PATH: settingsPath,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
      },
    })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', (chunk) => {
      const text = chunk.toString()
      stdout += text
      mainWindow?.webContents.send('archive-log', text)
    })

    child.stderr.on('data', (chunk) => {
      const text = chunk.toString()
      stderr += text
      mainWindow?.webContents.send('archive-log', text)
    })

    child.on('error', (error) => {
      emitArchiveLog(`归档启动失败：${error.message}`)
      reject(error)
    })

    child.on('close', (code) => {
      if (code !== 0) {
        const message = stderr || stdout || `Python process exited with code ${code}`
        emitArchiveLog(`归档失败：${message}`)
        reject(new Error(message))
        return
      }

      const match = stdout.match(/__BILIARCHIVE_RESULT__=(\{.*\})/s)
      if (!match) {
        emitArchiveLog('归档失败：未能从 Python 输出中解析结果。')
        reject(new Error('未能从 Python 输出中解析结果。'))
        return
      }

      try {
        const parsed = JSON.parse(match[1])
        emitArchiveLog(`归档完成：${parsed.markdownPath}`)
        resolve(parsed)
      } catch (error) {
        emitArchiveLog(`归档失败：${error instanceof Error ? error.message : String(error)}`)
        reject(error as Error)
      }
    })
  })
}

app.whenReady().then(() => {
  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

ipcMain.handle('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.handle('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('settings:load', () => loadSettings())

ipcMain.handle('settings:save', (_event, payload: RuntimeSettings) => saveSettings(payload))

ipcMain.handle('settings:status', async () => fetchSettingsStatus())

ipcMain.handle('dialog:pickDirectory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory'],
  })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.handle('archive:run', async (_event, payload: { video: string; generateAi: boolean }) => {
  return runPythonArchive(payload.video, payload.generateAi)
})

ipcMain.handle('shell:openPath', async (_event, targetPath: string) => {
  if (!targetPath) return
  await shell.openPath(targetPath)
})

ipcMain.handle('shell:showItem', async (_event, targetPath: string) => {
  if (!targetPath) return
  shell.showItemInFolder(targetPath)
})

ipcMain.handle('shell:openExternal', async (_event, targetUrl: string) => {
  if (!targetUrl) return
  await shell.openExternal(targetUrl)
})
