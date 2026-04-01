import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BookOpenText, ChevronDown, FolderOpen, Link2, LoaderCircle, ScanSearch, Rocket, Settings2, Star, X } from 'lucide-react'
import { useAppStore } from './store'
import appIcon from './assets/app_icon.png'

function getProgressState(logs: string[], running: boolean, status: string, hasResult: boolean) {
  if (hasResult) {
    return { percent: 100, label: '已完成' }
  }

  const joined = logs.join('\n')
  let percent = 6
  let label = running ? '准备中' : status

  if (/启动归档任务|已识别视频/.test(joined)) {
    percent = 14
    label = '识别视频'
  }
  if (/正在获取视频信息/.test(joined)) {
    percent = 28
    label = '获取信息'
  }
  if (/正在获取字幕|字幕获取完成|下载字幕/.test(joined)) {
    percent = 52
    label = '提取字幕'
  }
  if (/正在生成 AI 视频总结/.test(joined)) {
    percent = 76
    label = '生成总结'
  }
  if (/正在导出 Markdown/.test(joined)) {
    percent = 90
    label = '写入文件'
  }
  if (/归档完成|Markdown 已保存|Markdown 已导出|保存完成/.test(joined)) {
    percent = 100
    label = '已完成'
  }
  if (/归档失败|处理失败|启动失败/.test(`${joined}\n${status}`)) {
    percent = 100
    label = '失败'
  }

  return { percent, label }
}

function SettingsModal() {
  const { settings, setSettings, settingsOpen, setSettingsOpen, setSettingsStatus } = useAppStore()
  const [draft, setDraft] = useState(settings)

  useEffect(() => {
    setDraft(settings)
  }, [settings])

  const save = async () => {
    const next = await window.desktopAPI.saveSettings(draft)
    const status = await window.desktopAPI.loadSettingsStatus()
    setSettings(next)
    setSettingsStatus(status)
    setSettingsOpen(false)
  }

  const browse = async () => {
    const chosen = await window.desktopAPI.pickDirectory()
    if (chosen) {
      setDraft({ ...draft, output_dir: chosen })
    }
  }

  return (
    <AnimatePresence>
      {settingsOpen && (
        <motion.div
          className="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setSettingsOpen(false)}
        >
          <motion.div
            className="settings-modal glass-panel"
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.18 }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h2>客户端设置</h2>
              </div>
              <button className="icon-button" onClick={() => setSettingsOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <label className="field">
              <span>SESSDATA</span>
              <input
                type="password"
                value={draft.sessdata}
                onChange={(event) => setDraft({ ...draft, sessdata: event.target.value })}
                placeholder="只保存在本地配置文件"
              />
            </label>

            <label className="field">
              <span>MiniMax API Key</span>
              <input
                type="password"
                value={draft.minimax_api_key}
                onChange={(event) => setDraft({ ...draft, minimax_api_key: event.target.value })}
                placeholder="留空则跳过 AI 总结"
              />
            </label>

            <label className="field">
              <span>MiniMax 模型</span>
              <input
                value={draft.minimax_model}
                onChange={(event) => setDraft({ ...draft, minimax_model: event.target.value })}
              />
            </label>

            <label className="field">
              <span>Markdown 输出目录</span>
              <div className="inline-field">
                <input value={draft.output_dir} onChange={(event) => setDraft({ ...draft, output_dir: event.target.value })} />
                <button className="secondary-button" onClick={browse}>浏览</button>
              </div>
            </label>

            <div className="security-note">
              SESSDATA 和 API Key 只保存到本地 `.biliarchive.local.json`，不会写进源码。
            </div>

            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setSettingsOpen(false)}>
                取消
              </button>
              <button className="primary-button" onClick={save}>
                保存设置
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function HelpModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="settings-modal glass-panel help-modal"
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ duration: 0.18 }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div className="modal-title-row">
                <h2>使用说明</h2>
                <button
                  className="ghost-pill"
                  onClick={() => void window.desktopAPI.openExternal('https://github.com/UniqueYu8988/ZhiYuFox')}
                >
                  <Star size={13} className="star-lit" fill="currentColor" />
                  GitHub 项目地址
                </button>
              </div>
              <button className="icon-button" onClick={onClose}>
                <X size={18} />
              </button>
            </div>

            <div className="help-block">
              <h3>SESSDATA 获取方式</h3>
              <p>1. 先在浏览器登录 Bilibili。</p>
              <p>2. 打开任意 Bilibili 页面，按 F12 进入开发者工具。</p>
              <p>3. 在 Application 或 存储 页面找到 Cookies。</p>
              <p>4. 选择 https://www.bilibili.com 复制名为 `SESSDATA` 的值</p>
              <p>5. 回到知语狸，粘贴到设置中的 `SESSDATA` 字段即可。</p>
            </div>

            <div className="help-block">
              <h3>MiniMax API Key 获取</h3>
              <p>1. 登录 MiniMax 开放平台，先完成账户注册。</p>
              <p>2. 在“接口密钥”里创建新的 Key。</p>
              <p>• API Key：按次付费 丨 Token Plan Key：包月套餐</p>
              <p>• 推荐 Starter 连续包月套餐 ￥29（600 次调用 / 5 小时）</p>
              <p>• 使用我的邀请计划链接可享 9 折优惠。</p>
              <p>3. 复制 Key 到此程序（注意保管，以免泄露）</p>
            </div>

            <div className="help-block">
              <h3>免责声明</h3>
              <p>1. 生成的文件保存在本地，不会上传到云端。</p>
              <p>2. 产品基于字幕读取，仅适用于存在字幕/AI字幕的视频。</p>
              <p>3. 产品为非盈利项目，短期体验作者可提供 API Key。</p>
            </div>

            <button
              className="secondary-button help-action"
              onClick={() => void window.desktopAPI.openExternal('https://platform.minimaxi.com/docs/guides/quickstart')}
            >
              <Star size={14} className="star-lit" fill="currentColor" />
              MiniMax 开放平台
            </button>

            <button
              className="secondary-button help-action"
              onClick={() => void window.desktopAPI.openExternal('https://platform.minimaxi.com/subscribe/token-plan?code=BFyAjCS9Oq&source=link')}
            >
              <Star size={14} className="star-lit" fill="currentColor" />
              前往邀请计划链接
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function App() {
  const {
    videoInput,
    setVideoInput,
    logs,
    clearLogs,
    appendLog,
    status,
    setStatus,
    running,
    setRunning,
    setSettings,
    settingsStatus,
    setSettingsStatus,
    settingsLoaded,
    setSettingsLoaded,
    result,
    setResult,
    setSettingsOpen,
  } = useAppStore()
  const [logsOpen, setLogsOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const progress = getProgressState(logs, running, status, Boolean(result))

  useEffect(() => {
    void Promise.all([window.desktopAPI.loadSettings(), window.desktopAPI.loadSettingsStatus()]).then(([loaded, status]) => {
      setSettings(loaded)
      setSettingsStatus(status)
      setSettingsLoaded(true)
    })

    const unsubscribe = window.desktopAPI.onArchiveLog((message) => {
      appendLog(message)
    })

    return unsubscribe
  }, [appendLog, setSettings, setSettingsLoaded, setSettingsStatus])

  const run = async () => {
    if (!videoInput.trim() || running) return
    clearLogs()
    setResult(null)
    setLogsOpen(true)
    setRunning(true)
    setStatus('正在处理视频...')

    try {
      const response = await window.desktopAPI.runArchive({
        video: videoInput.trim(),
        generateAi: true,
      })
      setResult(response)
      setStatus(response.fileGenerated ? '处理完成，Markdown 已生成。' : (response.resultNote || '未生成文件'))
    } catch (error) {
      setStatus(error instanceof Error ? error.message : '处理失败')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="app-shell">
      <div className="window-frame">
        <div className="ambient ambient-left" />
        <div className="ambient ambient-right" />

        <header className="topbar">
          <div className="brand-block">
            <div className="brand-row">
              <img className="brand-logo" src={appIcon} alt="知语狸图标" />
              <h1>知语狸</h1>
            </div>
          </div>
          <div className="window-actions">
            <button className="icon-button" onClick={() => setHelpOpen(true)}>
              <BookOpenText size={15} />
            </button>
            <button className="icon-button" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={15} />
            </button>
            <button className="icon-button" onClick={() => void window.desktopAPI.close()}>
              <X size={15} />
            </button>
          </div>
        </header>

        <main className="workspace">
          <section className="hero">
            <div className="status-panel compact">
              <div className="status-line">
                <span className={settingsStatus.bilibili.valid ? 'status-badge ok' : 'status-badge'}>{settingsStatus.bilibili.valid ? '已登录' : '未配置'}</span>
                <span>{settingsStatus.bilibili.valid ? settingsStatus.bilibili.accountName : 'B站登录'}</span>
              </div>
              <div className="status-line">
                <span className={settingsStatus.minimax.valid ? 'status-badge ok' : 'status-badge'}>{settingsStatus.minimax.valid ? '已配置' : '未配置'}</span>
                <span>{settingsStatus.minimax.valid ? settingsStatus.minimax.model : 'MiniMax-M2.7'}</span>
              </div>
            </div>

            <label className="field">
              <span>视频链接 / BV 号</span>
              <div className="input-shell">
                <Link2 size={16} />
                <input
                  value={videoInput}
                  onChange={(event) => setVideoInput(event.target.value)}
                  placeholder="输入 BV 号或视频链接"
                />
              </div>
            </label>

            <div className="hero-actions">
              <button className="primary-button large" onClick={run} disabled={!videoInput.trim() || running || !settingsLoaded}>
                {running ? <LoaderCircle size={16} className="spin" /> : <Rocket size={16} />}
                <span>{running ? '生成中' : 'AI 视频总结'}</span>
                <span className="button-spacer" aria-hidden="true" />
              </button>
            </div>
          </section>

          <section className="stack-layout">
            <div className="section-block">
              <div className="section-head compact">
                <div className="section-title-wrap">
                  <h3>生成结果</h3>
                </div>
                {running || result ? (
                  <div className="progress-status" aria-label={`当前进度 ${progress.percent}%`}>
                    <div className="progress-copy">
                      <span>{progress.label}</span>
                      <strong>{progress.percent}%</strong>
                    </div>
                    <div className="progress-track">
                      <motion.div
                        className="progress-fill"
                        initial={false}
                        animate={{ width: `${progress.percent}%` }}
                        transition={{ duration: 0.28, ease: 'easeOut' }}
                      />
                    </div>
                  </div>
                ) : (
                  <span className="status-chip">{status}</span>
                )}
              </div>

              {result ? (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="result-list"
                >
                  <div className="result-card primary">
                    <span className="result-label">标题</span>
                    <strong>{result.videoTitle}</strong>
                  </div>
                  <div className="result-grid">
                    <div className="result-card">
                      <span className="result-label">日期</span>
                      <strong>{result.publishDate}</strong>
                    </div>
                    <div className="result-card">
                      <span className="result-label">字幕状态</span>
                      <strong>
                        {result.hasSubtitles
                          ? (result.pageCount > 1
                            ? `已获取 ${result.pagesWithSubtitles}/${result.pageCount} 个分P的字幕，共 ${result.subtitleEntryCount} 条`
                            : `已获取 ${result.subtitleGroupCount} 组字幕，共 ${result.subtitleEntryCount} 条`)
                          : (result.aiSkippedReason || '未检测到可用字幕，已跳过 AI 视频总结。')}
                      </strong>
                    </div>
                    {result.missingSubtitlePages.length > 0 && (
                      <div className="result-card warning">
                        <span className="result-label">未参与总结的分P</span>
                        <strong className="path-text">{result.missingSubtitlePages.join('；')}</strong>
                      </div>
                    )}
                    {!result.fileGenerated && (
                      <div className="result-card warning">
                        <span className="result-label">结果提示</span>
                        <strong>{result.resultNote || '未检测到可用字幕，未生成 Markdown 文件。'}</strong>
                      </div>
                    )}
                    {result.fileGenerated && (
                      <div className="result-card">
                        <span className="result-label">文件</span>
                        <strong className="path-text">{result.markdownPath}</strong>
                      </div>
                    )}
                  </div>
                  {result.fileGenerated && (
                    <div className="result-actions">
                      <button className="secondary-button" onClick={() => void window.desktopAPI.showItem(result.markdownPath)}>
                        <ScanSearch size={14} />
                        显示文件
                      </button>
                      <button className="secondary-button" onClick={() => void window.desktopAPI.openPath(result.outputDir)}>
                        <FolderOpen size={14} />
                        打开目录
                      </button>
                    </div>
                  )}
                </motion.div>
              ) : (
                <div className="empty-state compact" />
              )}
            </div>

            <div className="section-block log-section">
              <button className="log-toggle" onClick={() => setLogsOpen((value) => !value)}>
                <div className="section-title-wrap">
                  <h3>运行日志</h3>
                </div>
                <ChevronDown size={16} className={logsOpen ? 'chevron open' : 'chevron'} />
              </button>
              <AnimatePresence initial={false}>
                {logsOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="log-wrap"
                  >
                    <div className="log-list">
                      {logs.length > 0 ? logs.map((item, index) => (
                        <div className="log-entry" key={`${item}-${index}`}>
                          <span className="log-dot" />
                          <p>{item}</p>
                        </div>
                      )) : (
                        <div className="log-entry muted">
                          <span className="log-dot" />
                          <p>等待任务开始。</p>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </section>
        </main>

        <SettingsModal />
        <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
      </div>
    </div>
  )
}

export default App
