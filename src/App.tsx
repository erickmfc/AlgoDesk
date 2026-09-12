import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Bell, Bot, ChartNoAxesCombined, ChevronRight, CircleDollarSign,
  Gauge, LayoutDashboard, LockKeyhole, Network, Radio,
  RefreshCw, Search, Settings2, ShieldAlert, SlidersHorizontal, Square,
  WalletCards, X, Zap,
} from 'lucide-react'

type BotStatus = 'POSITION OPEN' | 'SCANNING' | 'WAITING' | 'HALTED'
type Tone = 'cyan' | 'violet' | 'amber' | 'red'
type FeedStatus = 'websocket' | 'rest' | 'offline'
type AccountStatus = 'loading' | 'connected' | 'not-configured' | 'error'
type BacktestMetrics = {
  equity: number
  return_percent: number
  max_drawdown_percent: number
  win_rate_percent: number
  profit_factor: number | null
  trades: number
  fees: number
  slippage: number
  exposure_percent: number
}
type PaperSummary = {
  equity: number
  daily_pnl: number
  drawdown_percent: number
  open_positions: number
  realized_pnl_24h: number
  win_rate_24h: number
  trades_24h: number
  bot_count: number
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

const bots: DeskBot[] = [
  { id: 'BOT-001', symbol: 'BTCUSDT', strategy: 'EMA Trend', status: 'POSITION OPEN', pnl: '+$124.32', pnlPct: '+0.42%', tone: 'cyan', position: 'LONG · 10%', activity: 'Paper snapshot: long on BTCUSDT' },
  { id: 'BOT-002', symbol: 'ETHUSDT', strategy: 'Mean Reversion', status: 'SCANNING', pnl: '+$38.90', pnlPct: '+0.18%', tone: 'violet', position: 'FLAT', activity: 'Scanning ETHUSDT for mean reversion opportunities' },
  { id: 'BOT-003', symbol: 'BTCUSDT', strategy: 'Mean Reversion', status: 'WAITING', pnl: '—', pnlPct: '—', tone: 'amber', position: 'FLAT', activity: 'No valid setup. Monitoring market structure' },
  { id: 'BOT-004', symbol: 'ETHUSDT', strategy: 'EMA Trend', status: 'SCANNING', pnl: '+$17.26', pnlPct: '+0.08%', tone: 'violet', position: 'FLAT', activity: 'Scanning ETHUSDT for trend setup' },
  { id: 'BOT-005', symbol: 'BTCUSDT', strategy: 'EMA Trend', status: 'HALTED', pnl: '-$36.21', pnlPct: '-0.14%', tone: 'red', position: 'FLAT', activity: 'Risk limit reached. Bot halted' },
]

const activities = [
  { time: '16:27', bot: 'BOT-002', label: 'SCANNING', tone: 'violet' as Tone, text: 'Scanning ETHUSDT for mean reversion opportunities' },
  { time: '16:26', bot: 'BOT-001', label: 'POSITION OPEN', tone: 'cyan' as Tone, text: 'Paper snapshot: long on BTCUSDT' },
  { time: '16:24', bot: 'BOT-003', label: 'WAITING', tone: 'amber' as Tone, text: 'No valid setup. Monitoring market structure' },
  { time: '16:22', bot: 'BOT-004', label: 'SCANNING', tone: 'violet' as Tone, text: 'Scanning ETHUSDT for trend setup' },
  { time: '16:18', bot: 'BOT-005', label: 'HALTED', tone: 'red' as Tone, text: 'Risk limit reached. Bot halted' },
  { time: '16:15', bot: 'BOT-001', label: 'CLOSED POSITION', tone: 'cyan' as Tone, text: 'Take profit hit. +$118.47' },
  { time: '16:12', bot: 'BOT-002', label: 'FOUND SETUP', tone: 'violet' as Tone, text: 'ETHUSDT mean reversion signal detected' },
  { time: '16:05', bot: 'BOT-004', label: 'CLOSED POSITION', tone: 'red' as Tone, text: 'Stop loss hit. -$36.21' },
]

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

function PageWorkspace({ page, botsOnline, onSelect, backtest }: { page: string; botsOnline: number; onSelect: (bot: DeskBot) => void; backtest: BacktestMetrics | null }) {
  const title = navItems.find((item) => item.id === page)?.label ?? 'Operations'
  if (page === 'operations') return null
  return <section className="workspace-panel">
    <div className="workspace-heading"><div><span className="section-kicker">ALGODESK / WORKSPACE</span><h2>{title}</h2><p>Superfície de controlo conectada ao motor paper trading.</p></div><button className="ghost-button"><RefreshCw size={15} /> Atualizar dados</button></div>
    <div className="workspace-grid">
      {page === 'bots' && bots.map((bot) => <button className="workspace-row" key={bot.id} onClick={() => onSelect(bot)}><BotAvatar status={bot.status} tone={bot.tone} /><div><strong>{bot.id}</strong><span>{bot.symbol} · {bot.strategy}</span></div><span className={`status-chip ${toneClass(bot.tone)}`}>{bot.status}</span><b>{bot.pnl}</b><ChevronRight size={16} /></button>)}
      {page === 'backtests' && <>
        <div className="detail-panel"><div className="panel-heading"><span>Demo backtest</span><StatusMark tone="violet" pulse /></div><h3>{backtest ? `${backtest.return_percent >= 0 ? '+' : ''}${backtest.return_percent.toFixed(2)}% return` : 'Loading research run'}</h3><p>Resultado determinístico para validar o pipeline; não é previsão de rentabilidade.</p><div className="progress-track"><span style={{ width: `${Math.min(100, Math.max(0, backtest?.win_rate_percent ?? 0))}%` }} /></div><small>{backtest ? `${backtest.trades} completed trade · ${backtest.win_rate_percent.toFixed(0)}% win rate` : 'Waiting for API'}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Research metrics</span><span className="positive">{backtest ? `$${backtest.equity.toFixed(2)}` : '—'}</span></div><div className="metric-list"><span>Max drawdown <b>{backtest ? `${backtest.max_drawdown_percent.toFixed(2)}%` : '—'}</b></span><span>Profit factor <b>{backtest?.profit_factor ?? '—'}</b></span><span>Exposure <b>{backtest ? `${backtest.exposure_percent.toFixed(1)}%` : '—'}</b></span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Trading frictions</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="amber" /><span>Fees</span><b>{backtest ? `$${backtest.fees.toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="amber" /><span>Slippage</span><b>{backtest ? `$${backtest.slippage.toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Lookahead</span><b>OFF</b></div></div>
      </>}
      {page !== 'bots' && page !== 'backtests' && <>
        <div className="detail-panel"><div className="panel-heading"><span>System overview</span><StatusMark tone="cyan" pulse /></div><h3>{title === 'Risk' ? 'Risk Engine armed' : `${title} is ready`}</h3><p>O ticker público da Binance é real; equity, PnL e eventos abaixo são um snapshot PAPER local até a conta ser conectada.</p><div className="progress-track"><span style={{ width: `${page === 'Risk' ? 68 : 84}%` }} /></div><small>{page === 'Risk' ? '68% of paper risk budget available' : `${botsOnline}/5 local paper processes healthy`}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Equity telemetry</span><span className="positive">+2.83%</span></div><Sparkline /><div className="chart-axis"><span>09:00</span><span>12:00</span><span>16:30</span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Guardrails</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="cyan" /><span>Live trading locked</span><b>ON</b></div><div className="guardrail"><StatusMark tone="amber" /><span>Paper mode</span><b>ACTIVE</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Spot only</span><b>ON</b></div></div>
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
  const [paperSummary, setPaperSummary] = useState<PaperSummary | null>(null)

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
    fetch(`${apiUrl}/api/backtests/demo`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { metrics?: BacktestMetrics } : Promise.reject(new Error('backtest request failed')))
      .then((payload) => setBacktestMetrics(payload.metrics ?? null))
      .catch(() => setBacktestMetrics(null))
  }, [])
  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
    fetch(`${apiUrl}/api/paper/summary`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as PaperSummary : Promise.reject(new Error('paper summary request failed')))
      .then((payload) => setPaperSummary(payload))
      .catch(() => setPaperSummary(null))
  }, [])

  const visibleBots = useMemo(() => bots.filter((bot) => `${bot.id} ${bot.symbol} ${bot.strategy} ${bot.status}`.toLowerCase().includes(search.toLowerCase())), [search])
  const botsOnline = bots.filter((bot) => bot.status !== 'HALTED').length
  const currentTime = clock.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const selectBot = (bot: DeskBot) => { setSelectedBot(bot); setNotice(`${bot.id} selecionado para inspeção`) }
  const navigate = (page: string) => {
    const item = navItems.find((candidate) => candidate.id === page)
    if (!item) return
    window.history.pushState({}, '', item.path)
    setActivePage(page)
  }
  const stopAll = () => { setHardStopped(true); setNotice('HARD STOP ativado · novas ordens bloqueadas') }
  const reenable = () => { if (enableText.trim() === 'ENABLE') { setHardStopped(false); setEnableText(''); setNotice('Motor reativado em modo PAPER') } else setNotice('Digite ENABLE para reativar o motor') }

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
        <div className="page-heading"><div><p className="section-kicker">TRADING CONTROL ROOM · BINANCE SPOT · PUBLIC TICKER</p><h1>{activePage === 'operations' ? 'Operations Desk' : navItems.find((item) => item.id === activePage)?.label}</h1><p className="heading-sub">{activePage === 'operations' ? 'Five paper bots. One mission. Disciplined execution.' : 'Observe, validate and keep every decision inside the guardrails.'}</p></div><div className="heading-controls"><div className="search-box"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a bot..." aria-label="Buscar bot" /></div><div className="mode-select"><span className="mode-dot" />PAPER · LIVE LOCKED<ChevronRight size={14} /></div></div></div>
        <div className="stats-row"><StatCard label="Paper equity snapshot" value={`$ ${(paperSummary?.equity ?? 12428.50).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} detail="Demo state · not Binance account" icon={WalletCards} /><StatCard label="Paper daily PnL" value={`$ ${(paperSummary?.daily_pnl ?? 342.18).toFixed(2)}`} detail="Demo state · not Binance PnL" tone="cyan" icon={CircleDollarSign} /><StatCard label="Paper drawdown" value={`${(paperSummary?.drawdown_percent ?? -3.12).toFixed(2)}%`} detail="Risk limit · 5.00%" tone="red" icon={Gauge} /><StatCard label="Bots online · local" value={`${botsOnline} / ${paperSummary?.bot_count ?? 5}`} detail="1 paper bot halted" tone="amber" icon={Bot} /><button className={`stop-button ${hardStopped ? 'is-stopped' : ''}`} onClick={hardStopped ? () => setHardStopped(false) : stopAll}><Square size={17} fill="currentColor" />{hardStopped ? 'HARD STOP ACTIVE' : 'PARAR TODOS OS ROBÔS'}</button></div>

        <PageWorkspace page={activePage} botsOnline={botsOnline} onSelect={selectBot} backtest={backtestMetrics} />
        {activePage === 'operations' && <div className="operations-grid">
          <section className="desk-panel"><div className="desk-panel-header"><div><span className="panel-eyebrow"><Radio size={13} /> PAPER SIMULATION</span><h2>Trading floor</h2></div><div className="desk-legend"><span><i className="legend-dot cyan" />Open</span><span><i className="legend-dot violet" />Scanning</span><span><i className="legend-dot amber" />Waiting</span><span><i className="legend-dot red" />Halted</span></div></div>
            <div className="trading-floor"><div className="floor-back-wall"><div className="wall-screen screen-map"><span>MARKET GRID</span><div className="world-dots" /></div><div className="wall-screen screen-chart"><span>BTC / ETH · BINANCE PUBLIC</span><div className="market-values"><b>₿ {livePrices.BTCUSDT ? `$${livePrices.BTCUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b><b>Ξ {livePrices.ETHUSDT ? `$${livePrices.ETHUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div><small className="market-source">{feedStatus === 'websocket' ? 'LIVE WEBSOCKET TICKER' : feedStatus === 'rest' ? 'LIVE REST TICKER' : 'NO LIVE MARKET FEED'}</small><Sparkline /></div><div className="wall-copy">DISCIPLINE<br /><em>BEATS</em><br />EMOTION</div></div><div className="floor-grid" /><div className="floor-light light-one" /><div className="floor-light light-two" />{visibleBots.map((bot, index) => <DeskStation bot={bot} index={index} key={bot.id} onSelect={() => selectBot(bot)} selected={selectedBot?.id === bot.id} />)}<div className="floor-label">ALGODESK <span>///</span> PAPER CONTROL FLOOR</div></div>
          </section>
          <aside className="activity-panel"><div className="activity-header"><div><span className="panel-eyebrow"><Activity size={13} /> PAPER SYSTEM LOG</span><h2>Activity feed</h2></div><button className="filter-button">All bots <ChevronRight size={13} /></button></div><div className="activity-list">{activities.map((item, index) => <button className="activity-item" key={`${item.time}-${index}`} onClick={() => { const bot = bots.find((candidate) => candidate.id === item.bot); if (bot) selectBot(bot) }}><div className="activity-rail"><StatusMark tone={item.tone} pulse={index === 0} /><span /></div><div className="activity-copy"><div className="activity-meta"><time>{item.time}</time><strong>{item.bot}</strong><em className={toneClass(item.tone)}>{item.label}</em></div><p>{item.text}</p></div></button>)}</div><button className="view-all">View full paper event log <ChevronRight size={14} /></button></aside>
        </div>}

        <footer className="bottom-strip"><div className="allocation"><span className="strip-label">PAPER PORTFOLIO ALLOCATION</span><div className="allocation-body"><div className="donut"><span>100%</span></div><div className="allocation-keys"><span><i className="legend-dot cyan" />BTCUSDT <b>48%</b></span><span><i className="legend-dot violet" />ETHUSDT <b>32%</b></span><span><i className="legend-dot sky" />Others <b>20%</b></span></div></div></div><div className="strip-stat"><span className="strip-label">PAPER OPEN POSITIONS</span><strong>{paperSummary?.open_positions ?? 2}</strong><small>Across 4 local bots</small></div><div className="strip-stat positive-stat"><span className="strip-label">PAPER REALIZED PNL · 24H</span><strong>+$ {(paperSummary?.realized_pnl_24h ?? 298.65).toFixed(2)}</strong><small>Snapshot · {paperSummary?.trades_24h ?? 12} trades</small></div><div className="strip-stat"><span className="strip-label">PAPER WIN RATE · 24H</span><strong>{(paperSummary?.win_rate_24h ?? 75).toFixed(0)}%</strong><small>Snapshot · 9 W / 3 L</small></div><div className="strip-stat"><span className="strip-label">AVG. TRADE DURATION</span><strong>1h 24m</strong><small>Paper execution</small></div><div className="system-status"><span className="strip-label">SYSTEM STATUS</span><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'websocket' ? 'Binance WebSocket' : feedStatus === 'rest' ? 'Binance REST connected' : 'Binance feed unavailable'}</div><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'offline' ? 'Market data offline' : 'Market data live'}</div><div><StatusMark tone={hardStopped ? 'red' : 'amber'} /> {hardStopped ? 'Paper engine halted' : 'Paper engine running'}</div><div><StatusMark tone={accountStatus === 'connected' ? 'cyan' : 'amber'} /> {accountStatus === 'connected' ? 'Account read-only connected' : accountStatus === 'not-configured' ? 'Account not configured' : accountStatus === 'loading' ? 'Account status loading' : 'Account read failed'}</div></div><div className="strip-pulse"><Sparkline /><span>{feedStatus === 'offline' ? 'OFFLINE' : 'STABLE'}</span></div></footer>
      </div>
    </main>

    {selectedBot && <div className="inspector"><div className="inspector-top"><span>BOT INSPECTOR</span><button onClick={() => setSelectedBot(null)} aria-label="Fechar inspetor"><X size={15} /></button></div><div className="inspector-hero"><BotAvatar status={selectedBot.status} tone={selectedBot.tone} /><div><strong>{selectedBot.id}</strong><span>{selectedBot.strategy}</span></div></div><div className="inspector-status"><StatusMark tone={selectedBot.tone} pulse={selectedBot.status === 'SCANNING'} /><b>{selectedBot.status}</b><span>• {selectedBot.position}</span></div><div className="inspector-grid"><div><small>SYMBOL</small><b>{selectedBot.symbol}</b></div><div><small>PnL</small><b className={selectedBot.tone === 'red' ? 'negative' : 'positive'}>{selectedBot.pnl}</b></div><div><small>TIMEFRAME</small><b>1H</b></div><div><small>RISK USED</small><b>0.25%</b></div></div><div className="inspector-chart"><span>POSITION TELEMETRY</span><Sparkline /></div><p className="inspector-note">{selectedBot.activity}</p><button className="inspector-action" onClick={() => setNotice(`${selectedBot.id}: ação manual bloqueada no modo PAPER`)}><SlidersHorizontal size={15} /> View strategy config</button></div>}

    {hardStopped && <div className="stop-modal-backdrop"><div className="stop-modal"><div className="modal-icon"><ShieldAlert size={22} /></div><span className="section-kicker">SAFETY INTERLOCK</span><h2>Hard stop active</h2><p>Novas ordens e ordens pendentes estão bloqueadas. Para reativar o motor PAPER, digite <strong>ENABLE</strong>.</p><input value={enableText} onChange={(event) => setEnableText(event.target.value)} placeholder="Digite ENABLE" autoFocus /><div className="modal-actions"><button className="ghost-button" onClick={() => { setHardStopped(false); setEnableText('') }}>Keep stopped</button><button className="primary-button" onClick={reenable}>Re-enable engine <Zap size={15} /></button></div></div></div>}
    {notice && <div className="toast"><StatusMark tone="cyan" />{notice}</div>}
  </div>
}

export default App
