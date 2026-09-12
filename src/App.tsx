import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Bell, Bot, ChartNoAxesCombined, ChevronRight, CircleDollarSign,
  Gauge, LayoutDashboard, LockKeyhole, Network, Radio,
  RefreshCw, Search, Settings2, ShieldAlert, SlidersHorizontal, Square,
  WalletCards, X, Zap,
} from 'lucide-react'

type BotStatus = 'POSITION OPEN' | 'SCANNING' | 'WAITING' | 'HALTED' | 'NOT DEPLOYED'
type Tone = 'cyan' | 'violet' | 'amber' | 'red'
type FeedStatus = 'websocket' | 'rest' | 'offline'
type AccountStatus = 'loading' | 'connected' | 'not-configured' | 'error'
type BacktestMetrics = {
  equity: number
  return_percent: number
  cagr_percent: number
  max_drawdown_percent: number
  win_rate_percent: number
  profit_factor: number | null
  trades: number
  fees: number
  slippage: number
  exposure_percent: number
  sharpe: number
  sortino: number
  average_win: number
  average_loss: number
  expectancy: number
  recovery_factor: number
  buy_hold_return_percent: number
}
type BacktestMeta = {
  data_points: number
  data_start: string
  data_end: string
  lookahead: boolean
}
type PaperSummary = {
  source?: string
  status?: string
  symbol?: string
  interval?: string
  equity: number
  daily_pnl: number
  drawdown_percent: number
  open_positions: number
  allocation_percent?: number
  last_run_at?: string | null
  last_candle_at?: string | null
  realized_pnl_24h: number
  win_rate_24h: number
  trades_24h: number
  bot_count: number
  hard_stop?: boolean
  last_error?: string | null
}
type SystemMetrics = {
  database_connected: boolean
  account_configured: boolean
  websocket_connections: number
  websocket_reconnects: number
  reconciliation_status: string
  last_market_event_at?: string | null
}
type RiskConfig = {
  max_position_percent: number
  max_total_exposure_percent: number
  hard_drawdown_limit_percent: number
  daily_loss_limit_percent: number
}
type PaperActivity = {
  time: string
  bot: string
  label: string
  tone: Tone
  text: string
}

type DeskBot = {
  id: string
  symbol: string
  strategy: string
  status: BotStatus
  pnl: string
  pnlPct: string
  tone: Tone
  position: string
  activity: string
}

const botTemplates = [
  { id: 'BOT-001', symbol: 'BTCUSDT', strategy: 'EMA Trend', tone: 'cyan' as Tone },
  { id: 'BOT-002', symbol: 'ETHUSDT', strategy: 'Mean Reversion', tone: 'violet' as Tone },
  { id: 'BOT-003', symbol: 'BTCUSDT', strategy: 'Mean Reversion', tone: 'amber' as Tone },
  { id: 'BOT-004', symbol: 'ETHUSDT', strategy: 'EMA Trend', tone: 'violet' as Tone },
  { id: 'BOT-005', symbol: 'BTCUSDT', strategy: 'EMA Trend', tone: 'amber' as Tone },
]

function formatSignedUsd(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  const sign = value < 0 ? '-$' : '+$'
  return `${sign}${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatSignedPercent(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return `${value < 0 ? '' : '+'}${value.toFixed(2)}%`
}

function buildDeskBots(summary: PaperSummary | null, hardStopped: boolean): DeskBot[] {
  const engineRunning = summary?.status === 'running'
  const activeStatus: BotStatus = hardStopped
    ? 'HALTED'
    : engineRunning
      ? summary.open_positions > 0 ? 'POSITION OPEN' : 'SCANNING'
      : 'WAITING'
  const activePnl = summary?.realized_pnl_24h ?? null
  const activePnlPct = summary?.equity ? (activePnl ?? 0) / summary.equity * 100 : null
  const activeSymbol = summary?.symbol ?? botTemplates[0].symbol
  return botTemplates.map((template, index) => index === 0
    ? {
      ...template,
      status: activeStatus,
      pnl: formatSignedUsd(activePnl),
      pnlPct: formatSignedPercent(activePnlPct),
      position: summary?.open_positions ? `OPEN · ${summary.allocation_percent?.toFixed(1) ?? '—'}%` : 'FLAT',
      activity: hardStopped
        ? 'Paper engine interlocked by the local safety control.'
        : engineRunning
          ? `Live paper engine on ${activeSymbol} using closed ${summary?.interval ?? '1h'} candles.`
          : 'Waiting for the paper engine to report a healthy Binance cycle.',
    }
    : {
      ...template,
      status: 'NOT DEPLOYED',
      pnl: '—',
      pnlPct: '—',
      position: 'FLAT',
      activity: 'Configured visual station only; no paper runtime is deployed for this strategy.',
    })
}

const navItems = [
  { id: 'operations', label: 'Operations', path: '/desk', icon: LayoutDashboard },
  { id: 'bots', label: 'Bots', path: '/bots', icon: Bot },
  { id: 'trades', label: 'Trades', path: '/trades', icon: Activity },
  { id: 'backtests', label: 'Backtests', path: '/backtests', icon: ChartNoAxesCombined },
  { id: 'risk', label: 'Risk', path: '/risk', icon: ShieldAlert },
  { id: 'system', label: 'System', path: '/system', icon: Network },
  { id: 'settings', label: 'Settings', path: '/settings', icon: Settings2 },
]

function pageForPath(pathname: string) {
  return navItems.find((item) => item.path === pathname)?.id ?? 'operations'
}

function toneClass(tone: Tone) { return `tone-${tone}` }

function StatusMark({ tone, pulse = false }: { tone: Tone; pulse?: boolean }) {
  return <span className={`status-mark ${toneClass(tone)} ${pulse ? 'is-pulsing' : ''}`} />
}

function BotAvatar({ status, tone }: { status: BotStatus; tone: Tone }) {
  return (
    <div className={`bot-avatar ${toneClass(tone)} state-${status.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="avatar-shadow" />
      <div className="avatar-body"><div className="avatar-chest-line" /></div>
      <div className="avatar-head"><div className="avatar-visor"><span /><span /></div><div className="avatar-ear left" /><div className="avatar-ear right" /></div>
      {status === 'SCANNING' && <div className="scan-beam" />}
    </div>
  )
}

function BotCard({ bot, onSelect, selected }: { bot: DeskBot; onSelect: () => void; selected: boolean }) {
  return (
    <button className={`bot-card ${toneClass(bot.tone)} ${selected ? 'is-selected' : ''}`} onClick={onSelect}>
      <span className="bot-card-top"><StatusMark tone={bot.tone} pulse={bot.status === 'SCANNING'} /><strong>{bot.id}</strong><ChevronRight size={14} /></span>
      <span className="bot-card-meta">{bot.symbol}<i />{bot.strategy}</span>
      <span className={`status-chip ${toneClass(bot.tone)}`}>{bot.status}</span>
      <span className="bot-card-pnl"><b>{bot.pnl}</b><small>{bot.pnlPct}</small></span>
    </button>
  )
}

function DeskStation({ bot, index, onSelect, selected }: { bot: DeskBot; index: number; onSelect: () => void; selected: boolean }) {
  return (
    <div className={`desk-station station-${index + 1} ${toneClass(bot.tone)} ${selected ? 'is-selected' : ''}`}>
      <div className="station-card"><BotCard bot={bot} onSelect={onSelect} selected={selected} /></div>
      <div className="desk-surface"><div className="monitor monitor-a"><div className="chart-lines" /></div><div className="monitor monitor-b"><div className="chart-bars"><i /><i /><i /><i /><i /><i /></div></div><div className="desk-keyboard" /></div>
      <BotAvatar status={bot.status} tone={bot.tone} />
      <div className="chair" />
    </div>
  )
}

function Sparkline() {
  return <svg className="sparkline" viewBox="0 0 180 44" preserveAspectRatio="none" aria-label="Equity sparkline"><path d="M0 30 C10 25 15 33 25 27 S40 12 50 25 S66 36 75 20 S92 26 100 17 S118 20 128 9 S146 26 155 16 S167 14 180 4" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M0 30 C10 25 15 33 25 27 S40 12 50 25 S66 36 75 20 S92 26 100 17 S118 20 128 9 S146 26 155 16 S167 14 180 4 L180 44 L0 44Z" fill="currentColor" opacity=".08" /></svg>
}

function StatCard({ label, value, detail, tone = 'cyan', icon: Icon }: { label: string; value: string; detail: string; tone?: Tone; icon: typeof Activity }) {
  return <div className={`stat-card ${toneClass(tone)}`}><div className="stat-header"><span>{label}</span><Icon size={16} /></div><strong>{value}</strong><small>{detail}</small></div>
}

function PageWorkspace({ page, bots, botsOnline, onSelect, backtest, backtestMeta, backtestState, paperSummary, systemMetrics, riskConfig }: { page: string; bots: DeskBot[]; botsOnline: number; onSelect: (bot: DeskBot) => void; backtest: BacktestMetrics | null; backtestMeta: BacktestMeta | null; backtestState: 'loading' | 'ready' | 'error'; paperSummary: PaperSummary | null; systemMetrics: SystemMetrics | null; riskConfig: RiskConfig | null }) {
  const title = navItems.find((item) => item.id === page)?.label ?? 'Operations'
  const paperRunning = paperSummary?.status === 'running'
  const drawdown = Math.abs(paperSummary?.drawdown_percent ?? 0)
  const drawdownLimit = riskConfig?.hard_drawdown_limit_percent ?? 5
  const riskBudgetUsed = drawdownLimit ? Math.min(100, drawdown / drawdownLimit * 100) : 0
  const dataHealthy = Boolean(systemMetrics?.database_connected && paperRunning)
  if (page === 'operations') return null
  return <section className="workspace-panel">
    <div className="workspace-heading"><div><span className="section-kicker">ALGODESK / WORKSPACE</span><h2>{title}</h2><p>Superfície de controlo conectada ao motor paper trading.</p></div><button className="ghost-button"><RefreshCw size={15} /> Atualizar dados</button></div>
    <div className="workspace-grid">
      {page === 'bots' && bots.map((bot) => <button className="workspace-row" key={bot.id} onClick={() => onSelect(bot)}><BotAvatar status={bot.status} tone={bot.tone} /><div><strong>{bot.id}</strong><span>{bot.symbol} · {bot.strategy}</span></div><span className={`status-chip ${toneClass(bot.tone)}`}>{bot.status}</span><b>{bot.pnl}</b><ChevronRight size={16} /></button>)}
      {page === 'backtests' && <>
        <div className="detail-panel"><div className="panel-heading"><span>Binance historical backtest</span><StatusMark tone={backtestState === 'error' ? 'amber' : 'violet'} pulse={backtestState === 'loading'} /></div><h3>{backtest ? `${backtest.return_percent >= 0 ? '+' : ''}${backtest.return_percent.toFixed(2)}% return` : backtestState === 'error' ? 'Research data unavailable' : 'Loading Binance history'}</h3><p>{backtestMeta ? `${backtestMeta.data_points} closed BTCUSDT candles · ${backtestMeta.data_start.slice(0, 10)} → ${backtestMeta.data_end.slice(0, 10)}` : backtestState === 'error' ? 'A Binance historical request failed; no synthetic result is shown.' : 'Fetching closed candles from Binance Spot.'}</p><div className="progress-track"><span style={{ width: `${Math.min(100, Math.max(0, backtest?.win_rate_percent ?? 0))}%` }} /></div><small>{backtest ? `${backtest.trades} completed trade · ${backtest.win_rate_percent.toFixed(0)}% win rate` : backtestState === 'error' ? 'Waiting for a healthy market-data response' : 'Waiting for API'}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Research metrics</span><span className="positive">{backtest ? `$${backtest.equity.toFixed(2)}` : '—'}</span></div><div className="metric-list"><span>Max drawdown <b>{backtest ? `${backtest.max_drawdown_percent.toFixed(2)}%` : '—'}</b></span><span>Profit factor <b>{backtest ? backtest.profit_factor === null ? '—' : backtest.profit_factor.toFixed(2) : '—'}</b></span><span>Exposure <b>{backtest ? `${backtest.exposure_percent.toFixed(1)}%` : '—'}</b></span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Trading frictions</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="amber" /><span>Fees</span><b>{backtest ? `$${backtest.fees.toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="amber" /><span>Slippage</span><b>{backtest ? `$${backtest.slippage.toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Lookahead</span><b>OFF</b></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Performance</span><span className="positive">{backtest ? `${backtest.cagr_percent.toFixed(2)}% CAGR` : '—'}</span></div><div className="metric-list"><span>Sharpe <b>{backtest ? backtest.sharpe.toFixed(2) : '—'}</b></span><span>Sortino <b>{backtest ? backtest.sortino.toFixed(2) : '—'}</b></span><span>Buy &amp; hold <b>{backtest ? `${backtest.buy_hold_return_percent.toFixed(2)}%` : '—'}</b></span></div></div>
      </>}
      {page !== 'bots' && page !== 'backtests' && <>
        <div className="detail-panel"><div className="panel-heading"><span>System overview</span><StatusMark tone={dataHealthy ? 'cyan' : 'amber'} pulse={dataHealthy} /></div><h3>{title === 'Risk' ? (paperRunning ? 'Risk Engine armed' : 'Risk telemetry waiting') : title === 'System' ? (systemMetrics?.database_connected ? 'System healthy' : 'System unavailable') : title === 'Trades' ? `${paperSummary?.trades_24h ?? 0} closed paper trades` : `${title} is ready`}</h3><p>{title === 'Risk' ? 'Risk is evaluated before each paper intent; no live order path is enabled.' : title === 'System' ? 'Runtime health comes from the FastAPI readiness and metrics endpoints.' : title === 'Trades' ? 'The list is backed by the paper engine events generated from closed Binance candles.' : 'Public Binance market data is live; account data remains read-only and optional.'}</p><div className="progress-track"><span style={{ width: `${title === 'Risk' ? riskBudgetUsed : dataHealthy ? 100 : 0}%` }} /></div><small>{title === 'Risk' ? `${drawdown.toFixed(2)}% drawdown used · limit ${drawdownLimit.toFixed(2)}%` : title === 'System' ? `${systemMetrics?.websocket_connections ?? 0} market stream connection(s) · ${systemMetrics?.websocket_reconnects ?? 0} reconnect(s)` : `${botsOnline}/5 visual stations backed by a deployed paper engine`}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Equity telemetry</span><span className={paperSummary && paperSummary.daily_pnl >= 0 ? 'positive' : 'negative'}>{paperSummary ? formatSignedUsd(paperSummary.daily_pnl) : '—'}</span></div><Sparkline /><div className="chart-axis"><span>Paper start</span><span>{paperSummary?.last_candle_at ? new Date(paperSummary.last_candle_at).toLocaleDateString('pt-BR') : '—'}</span><span>{paperSummary?.last_run_at ? new Date(paperSummary.last_run_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}</span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Guardrails</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="cyan" /><span>Live trading locked</span><b>ON</b></div><div className="guardrail"><StatusMark tone={paperRunning ? 'amber' : 'red'} /><span>Paper mode</span><b>{paperRunning ? 'ACTIVE' : 'WAITING'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Spot only</span><b>ON</b></div></div>
      </>}
    </div>
  </section>
}

function App() {
  const [activePage, setActivePage] = useState(() => pageForPath(window.location.pathname))
  const [selectedBot, setSelectedBot] = useState<DeskBot | null>(null)
  const [search, setSearch] = useState('')
  const [hardStopped, setHardStopped] = useState(false)
  const [enableText, setEnableText] = useState('')
  const [notice, setNotice] = useState('')
  const [clock, setClock] = useState(new Date())
  const [livePrices, setLivePrices] = useState<Record<string, number>>({})
  const [feedStatus, setFeedStatus] = useState<FeedStatus>('offline')
  const [accountStatus, setAccountStatus] = useState<AccountStatus>('loading')
  const [backtestMetrics, setBacktestMetrics] = useState<BacktestMetrics | null>(null)
  const [backtestMeta, setBacktestMeta] = useState<BacktestMeta | null>(null)
  const [backtestState, setBacktestState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [paperSummary, setPaperSummary] = useState<PaperSummary | null>(null)
  const [paperActivities, setPaperActivities] = useState<PaperActivity[]>([])
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null)
  const [riskConfig, setRiskConfig] = useState<RiskConfig | null>(null)

  useEffect(() => { const timer = window.setInterval(() => setClock(new Date()), 1000); return () => window.clearInterval(timer) }, [])
  useEffect(() => {
    const onPopState = () => setActivePage(pageForPath(window.location.pathname))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(''), 3600); return () => window.clearTimeout(timer) }, [notice])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const wsUrl = import.meta.env.VITE_WS_URL ?? apiUrl.replace(/^http/, 'ws')
    let socket: WebSocket | undefined
    let disposed = false
    const loadMarket = async () => {
      try {
        const response = await fetch(`${apiUrl}/api/market/ticker?symbol=BTCUSDT,ETHUSDT`, { cache: 'no-store' })
        if (!response.ok) throw new Error('market request failed')
        const payload = await response.json() as { tickers?: Array<{ symbol: string; price: number }> }
        const nextPrices = Object.fromEntries((payload.tickers ?? []).filter((ticker) => Number.isFinite(ticker.price) && ticker.price > 0).map((ticker) => [ticker.symbol, ticker.price]))
        if (!Object.keys(nextPrices).length) throw new Error('empty market response')
        if (!disposed) {
          setLivePrices((current) => ({ ...current, ...nextPrices }))
          if (!socket || socket.readyState !== WebSocket.OPEN) setFeedStatus('rest')
        }
      } catch { if (!disposed) { setFeedStatus('offline'); setLivePrices({}) } }
    }
    void loadMarket()
    try {
      socket = new WebSocket(`${wsUrl}/ws/market?symbols=BTCUSDT,ETHUSDT`)
      socket.addEventListener('open', () => { if (!disposed) setFeedStatus('websocket') })
      socket.addEventListener('message', (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string; symbol?: string; price?: number }
          const price = payload.price
          if (!disposed && payload.type === 'ticker' && payload.symbol && typeof price === 'number' && Number.isFinite(price) && price > 0) {
            setLivePrices((current) => ({ ...current, [payload.symbol as string]: price }))
            setFeedStatus('websocket')
          }
        } catch { /* Ignore malformed stream frames; REST remains the fallback. */ }
      })
      socket.addEventListener('close', () => { if (!disposed) setFeedStatus((current) => current === 'websocket' ? 'offline' : current) })
    } catch { setFeedStatus('offline') }
    const timer = window.setInterval(loadMarket, 15000)
    return () => { disposed = true; socket?.close(); window.clearInterval(timer) }
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    fetch(`${apiUrl}/api/account/summary`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { connected?: boolean; configured?: boolean } : Promise.reject(new Error('account request failed')))
      .then((payload) => setAccountStatus(payload.connected ? 'connected' : payload.configured ? 'error' : 'not-configured'))
      .catch(() => setAccountStatus('error'))
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    fetch(`${apiUrl}/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=500`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { metrics?: BacktestMetrics; data_points?: number; data_start?: string; data_end?: string; lookahead?: boolean } : Promise.reject(new Error('backtest request failed')))
      .then((payload) => {
        setBacktestMetrics(payload.metrics ?? null)
        setBacktestMeta(payload.data_points && payload.data_start && payload.data_end ? { data_points: payload.data_points, data_start: payload.data_start, data_end: payload.data_end, lookahead: payload.lookahead ?? false } : null)
        setBacktestState(payload.metrics ? 'ready' : 'error')
      })
      .catch(() => { setBacktestMetrics(null); setBacktestMeta(null); setBacktestState('error') })
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const loadPaper = () => fetch(`${apiUrl}/api/paper/summary`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as PaperSummary : Promise.reject(new Error('paper summary request failed')))
      .then((payload) => { setPaperSummary(payload); setHardStopped(payload.hard_stop ?? false) })
      .catch(() => setPaperSummary(null))
    void loadPaper()
    const timer = window.setInterval(loadPaper, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const loadEvents = () => fetch(`${apiUrl}/api/paper/events`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { events?: PaperActivity[] } : Promise.reject(new Error('paper events request failed')))
      .then((payload) => setPaperActivities(payload.events ?? []))
      .catch(() => setPaperActivities([]))
    void loadEvents()
    const timer = window.setInterval(loadEvents, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    const loadSystemMetrics = () => fetch(`${apiUrl}/api/system/metrics`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as SystemMetrics : Promise.reject(new Error('system metrics request failed')))
      .then((payload) => setSystemMetrics(payload))
      .catch(() => setSystemMetrics(null))
    void loadSystemMetrics()
    const timer = window.setInterval(loadSystemMetrics, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    fetch(`${apiUrl}/api/risk`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { config?: RiskConfig } : Promise.reject(new Error('risk request failed')))
      .then((payload) => setRiskConfig(payload.config ?? null))
      .catch(() => setRiskConfig(null))
  }, [])

  const bots = useMemo(() => buildDeskBots(paperSummary, hardStopped), [paperSummary, hardStopped])
  const visibleBots = useMemo(() => bots.filter((bot) => `${bot.id} ${bot.symbol} ${bot.strategy} ${bot.status}`.toLowerCase().includes(search.toLowerCase())), [bots, search])
  const botsOnline = paperSummary?.status === 'running' ? paperSummary.bot_count : 0
  const currentTime = clock.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const displayActivities: PaperActivity[] = paperActivities.length ? paperActivities : [{ time: '—', bot: 'PAPER', label: paperSummary?.status === 'error' ? 'ERROR' : 'WAITING', tone: paperSummary?.status === 'error' ? 'red' : 'amber', text: paperSummary?.status === 'error' ? (paperSummary.last_error ?? 'Paper engine unavailable') : 'Waiting for the first closed-candle signal' }]

  const selectBot = (bot: DeskBot) => { setSelectedBot(bot); setNotice(`${bot.id} selecionado para inspeção`) }
  const navigate = (page: string) => {
    const item = navItems.find((candidate) => candidate.id === page)
    if (!item) return
    window.history.pushState({}, '', item.path)
    setActivePage(page)
  }
  const setPaperKillSwitch = async (enabled: boolean, confirmation?: string) => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    try {
      const response = await fetch(`${apiUrl}/api/paper/kill-switch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, confirmation }) })
      if (!response.ok) throw new Error((await response.json() as { detail?: string }).detail ?? 'kill switch request failed')
      const payload = await response.json() as { paper?: PaperSummary }
      setPaperSummary(payload.paper ?? null)
      setHardStopped(enabled)
      setNotice(enabled ? 'HARD STOP ativado no motor PAPER' : 'Motor PAPER reativado')
      if (!enabled) { setEnableText(''); }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Não foi possível atualizar o HARD STOP')
      if (enabled) setHardStopped(false)
    }
  }
  const stopAll = () => { setHardStopped(true); void setPaperKillSwitch(true) }
  const reenable = () => { if (enableText.trim() === 'ENABLE') void setPaperKillSwitch(false, 'ENABLE'); else setNotice('Digite ENABLE para reativar o motor') }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><span /><span /><span /></div>
      <div className="brand-word">ALG<span>O</span></div>
      <div className="nav-list">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => navigate(id)}><Icon size={19} strokeWidth={1.7} /><span>{label}</span></button>)}</div>
      <div className="sidebar-bottom"><div className="side-divider" /><button className="nav-item"><Network size={18} /><span>Connect</span></button><span className="version">v0.1.0 · PAPER</span></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumb"><span>ALGODESK</span><ChevronRight size={14} /><b>{navItems.find((item) => item.id === activePage)?.label.toUpperCase()}</b></div><div className="top-actions"><span className={`connection ${feedStatus === 'offline' ? 'is-offline' : ''}`}><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'websocket' ? 'Binance WebSocket' : feedStatus === 'rest' ? 'Binance REST connected' : 'Binance feed unavailable'}</span><span className="top-time">{currentTime} BRT</span><button className="icon-button" aria-label="Notificações"><Bell size={17} /></button><button className="avatar-user">AD</button><span className="user-name">AlgoTrader</span></div></header>

      <div className="content">
        <div className="page-heading"><div><p className="section-kicker">TRADING CONTROL ROOM · BINANCE SPOT · PUBLIC TICKER</p><h1>{activePage === 'operations' ? 'Operations Desk' : navItems.find((item) => item.id === activePage)?.label}</h1><p className="heading-sub">{activePage === 'operations' ? 'One deployed paper engine. Five transparent visual stations.' : 'Observe, validate and keep every decision inside the guardrails.'}</p></div><div className="heading-controls"><div className="search-box"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a bot..." aria-label="Buscar bot" /></div><div className="mode-select"><span className="mode-dot" />PAPER · LIVE LOCKED<ChevronRight size={14} /></div></div></div>
        <div className="stats-row"><StatCard label="Paper equity · real market" value={paperSummary ? `$ ${paperSummary.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} detail={paperSummary?.status === 'running' ? 'Engine · Binance closed candles' : 'Engine warming up'} icon={WalletCards} /><StatCard label="Paper realized PnL" value={formatSignedUsd(paperSummary?.daily_pnl)} detail={paperSummary?.status === 'running' ? 'Since paper session start' : 'Awaiting paper engine'} tone="cyan" icon={CircleDollarSign} /><StatCard label="Paper drawdown" value={paperSummary ? `${paperSummary.drawdown_percent.toFixed(2)}%` : '—'} detail={`Risk limit · ${(riskConfig?.hard_drawdown_limit_percent ?? 5).toFixed(2)}%`} tone="red" icon={Gauge} /><StatCard label="Bots online · local" value={`${botsOnline} / ${bots.length}`} detail="Only deployed engines count as online" tone="amber" icon={Bot} /><button className={`stop-button ${hardStopped ? 'is-stopped' : ''}`} onClick={hardStopped ? () => setHardStopped(false) : stopAll}><Square size={17} fill="currentColor" />{hardStopped ? 'HARD STOP ACTIVE' : 'PARAR TODOS OS ROBÔS'}</button></div>

      <PageWorkspace page={activePage} bots={bots} botsOnline={botsOnline} onSelect={selectBot} backtest={backtestMetrics} backtestMeta={backtestMeta} backtestState={backtestState} paperSummary={paperSummary} systemMetrics={systemMetrics} riskConfig={riskConfig} />
        {activePage === 'operations' && <div className="operations-grid">
          <section className="desk-panel"><div className="desk-panel-header"><div><span className="panel-eyebrow"><Radio size={13} /> PAPER SIMULATION</span><h2>Trading floor</h2></div><div className="desk-legend"><span><i className="legend-dot cyan" />Open</span><span><i className="legend-dot violet" />Scanning</span><span><i className="legend-dot amber" />Waiting</span><span><i className="legend-dot red" />Halted</span></div></div>
            <div className="trading-floor"><div className="floor-back-wall"><div className="wall-screen screen-map"><span>MARKET GRID</span><div className="world-dots" /></div><div className="wall-screen screen-chart"><span>BTC / ETH · BINANCE PUBLIC</span><div className="market-values"><b>₿ {livePrices.BTCUSDT ? `$${livePrices.BTCUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b><b>Ξ {livePrices.ETHUSDT ? `$${livePrices.ETHUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div><small className="market-source">{feedStatus === 'websocket' ? 'LIVE WEBSOCKET TICKER' : feedStatus === 'rest' ? 'LIVE REST TICKER' : 'NO LIVE MARKET FEED'}</small><Sparkline /></div><div className="wall-copy">DISCIPLINE<br /><em>BEATS</em><br />EMOTION</div></div><div className="floor-grid" /><div className="floor-light light-one" /><div className="floor-light light-two" />{visibleBots.map((bot, index) => <DeskStation bot={bot} index={index} key={bot.id} onSelect={() => selectBot(bot)} selected={selectedBot?.id === bot.id} />)}<div className="floor-label">ALGODESK <span>///</span> PAPER CONTROL FLOOR</div></div>
          </section>
          <aside className="activity-panel"><div className="activity-header"><div><span className="panel-eyebrow"><Activity size={13} /> PAPER SYSTEM LOG</span><h2>Activity feed</h2></div><button className="filter-button">All bots <ChevronRight size={13} /></button></div><div className="activity-list">{displayActivities.map((item, index) => <button className="activity-item" key={`${item.time}-${index}`} onClick={() => { const bot = bots.find((candidate) => candidate.id === item.bot || (candidate.id === 'BOT-001' && item.bot === 'ema-btc-01')); if (bot) selectBot(bot) }}><div className="activity-rail"><StatusMark tone={item.tone} pulse={index === 0} /><span /></div><div className="activity-copy"><div className="activity-meta"><time>{item.time}</time><strong>{item.bot}</strong><em className={toneClass(item.tone)}>{item.label}</em></div><p>{item.text}</p></div></button>)}</div><button className="view-all">View full paper event log <ChevronRight size={14} /></button></aside>
        </div>}

        <footer className="bottom-strip"><div className="allocation"><span className="strip-label">PAPER PORTFOLIO ALLOCATION</span><div className="allocation-body"><div className="donut" style={{ background: `conic-gradient(var(--cyan) 0 ${paperSummary?.allocation_percent ?? 0}%, #18364c ${paperSummary?.allocation_percent ?? 0}% 100%)` }}><span>{(paperSummary?.allocation_percent ?? 0).toFixed(0)}%</span></div><div className="allocation-keys"><span><i className="legend-dot cyan" />{paperSummary?.symbol ?? 'BTCUSDT'} <b>{(paperSummary?.allocation_percent ?? 0).toFixed(0)}%</b></span></div></div></div><div className="strip-stat"><span className="strip-label">PAPER OPEN POSITIONS</span><strong>{paperSummary?.open_positions ?? 0}</strong><small>Active paper engine</small></div><div className="strip-stat positive-stat"><span className="strip-label">PAPER REALIZED PNL</span><strong>{formatSignedUsd(paperSummary?.realized_pnl_24h)}</strong><small>Engine · {paperSummary?.trades_24h ?? 0} closed trades</small></div><div className="strip-stat"><span className="strip-label">PAPER WIN RATE</span><strong>{paperSummary ? `${paperSummary.win_rate_24h.toFixed(0)}%` : '—'}</strong><small>Realized paper trades</small></div><div className="strip-stat"><span className="strip-label">DATA SOURCE</span><strong>BINANCE</strong><small>Closed {paperSummary?.interval ?? '1h'} candles</small></div><div className="system-status"><span className="strip-label">SYSTEM STATUS</span><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'websocket' ? 'Binance WebSocket' : feedStatus === 'rest' ? 'Binance REST connected' : 'Binance feed unavailable'}</div><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'offline' ? 'Market data offline' : 'Market data live'}</div><div><StatusMark tone={hardStopped ? 'red' : 'amber'} /> {hardStopped ? 'Paper engine halted' : paperSummary?.status === 'error' ? 'Paper engine error' : paperSummary?.status === 'running' ? 'Paper engine running' : 'Paper engine starting'}</div><div><StatusMark tone={accountStatus === 'connected' ? 'cyan' : 'amber'} /> {accountStatus === 'connected' ? 'Account read-only connected' : accountStatus === 'not-configured' ? 'Account not configured' : accountStatus === 'loading' ? 'Account status loading' : 'Account read failed'}</div></div><div className="strip-pulse"><Sparkline /><span>{feedStatus === 'offline' ? 'OFFLINE' : 'STABLE'}</span></div></footer>
      </div>
    </main>

    {selectedBot && <div className="inspector"><div className="inspector-top"><span>BOT INSPECTOR</span><button onClick={() => setSelectedBot(null)} aria-label="Fechar inspetor"><X size={15} /></button></div><div className="inspector-hero"><BotAvatar status={selectedBot.status} tone={selectedBot.tone} /><div><strong>{selectedBot.id}</strong><span>{selectedBot.strategy}</span></div></div><div className="inspector-status"><StatusMark tone={selectedBot.tone} pulse={selectedBot.status === 'SCANNING'} /><b>{selectedBot.status}</b><span>• {selectedBot.position}</span></div><div className="inspector-grid"><div><small>SYMBOL</small><b>{selectedBot.symbol}</b></div><div><small>PnL</small><b className={selectedBot.pnl.startsWith('-') ? 'negative' : 'positive'}>{selectedBot.pnl}</b></div><div><small>TIMEFRAME</small><b>{paperSummary?.interval ?? '1h'}</b></div><div><small>RISK LIMIT</small><b>{riskConfig ? `${riskConfig.max_position_percent.toFixed(2)}%` : '—'}</b></div></div><div className="inspector-chart"><span>POSITION TELEMETRY</span><Sparkline /></div><p className="inspector-note">{selectedBot.activity}</p><button className="inspector-action" onClick={() => setNotice(`${selectedBot.id}: ação manual bloqueada no modo PAPER`)}><SlidersHorizontal size={15} /> View strategy config</button></div>}

    {hardStopped && <div className="stop-modal-backdrop"><div className="stop-modal"><div className="modal-icon"><ShieldAlert size={22} /></div><span className="section-kicker">SAFETY INTERLOCK</span><h2>Hard stop active</h2><p>Novas ordens e ordens pendentes estão bloqueadas no motor PAPER. Para reativar, digite <strong>ENABLE</strong>.</p><input value={enableText} onChange={(event) => setEnableText(event.target.value)} placeholder="Digite ENABLE" autoFocus /><div className="modal-actions"><button className="ghost-button" onClick={() => setNotice('HARD STOP permanece ativo')}>Keep stopped</button><button className="primary-button" onClick={reenable}>Re-enable engine <Zap size={15} /></button></div></div></div>}
    {notice && <div className="toast"><StatusMark tone="cyan" />{notice}</div>}
  </div>
}

export default App
