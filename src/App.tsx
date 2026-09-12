import { useEffect, useMemo, useState } from 'react'
import {
  Activity, Bell, Bot, ChartNoAxesCombined, ChevronRight, CircleDollarSign,
  Gauge, LayoutDashboard, LineChart, LockKeyhole, Network, Radio, Radar,
  RefreshCw, Search, Settings2, ShieldAlert, SlidersHorizontal, Square,
  Terminal, WalletCards, Wifi, X, Zap,
} from 'lucide-react'

type BotStatus = 'POSITION OPEN' | 'SCANNING' | 'WAITING' | 'HALTED'
type Tone = 'cyan' | 'violet' | 'amber' | 'red'

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
  { id: 'BOT-001', symbol: 'BTCUSDT', strategy: 'EMA Trend', status: 'POSITION OPEN', pnl: '+$124.32', pnlPct: '+0.42%', tone: 'cyan', position: 'LONG · 10%', activity: 'Opened long on BTCUSDT at 62,340.10' },
  { id: 'BOT-002', symbol: 'ETHUSDT', strategy: 'Mean Reversion', status: 'SCANNING', pnl: '+$38.90', pnlPct: '+0.18%', tone: 'violet', position: 'FLAT', activity: 'Scanning ETHUSDT for mean reversion opportunities' },
  { id: 'BOT-003', symbol: 'BTCUSDT', strategy: 'Mean Reversion', status: 'WAITING', pnl: '—', pnlPct: '—', tone: 'amber', position: 'FLAT', activity: 'No valid setup. Monitoring market structure' },
  { id: 'BOT-004', symbol: 'ETHUSDT', strategy: 'EMA Trend', status: 'SCANNING', pnl: '+$17.26', pnlPct: '+0.08%', tone: 'violet', position: 'FLAT', activity: 'Scanning ETHUSDT for trend setup' },
  { id: 'BOT-005', symbol: 'BTCUSDT', strategy: 'EMA Trend', status: 'HALTED', pnl: '-$36.21', pnlPct: '-0.14%', tone: 'red', position: 'FLAT', activity: 'Risk limit reached. Bot halted' },
]

const activities = [
  { time: '16:27', bot: 'BOT-002', label: 'SCANNING', tone: 'violet' as Tone, text: 'Scanning ETHUSDT for mean reversion opportunities' },
  { time: '16:26', bot: 'BOT-001', label: 'POSITION OPEN', tone: 'cyan' as Tone, text: 'Opened long on BTCUSDT at 62,340.10' },
  { time: '16:24', bot: 'BOT-003', label: 'WAITING', tone: 'amber' as Tone, text: 'No valid setup. Monitoring market structure' },
  { time: '16:22', bot: 'BOT-004', label: 'SCANNING', tone: 'violet' as Tone, text: 'Scanning ETHUSDT for trend setup' },
  { time: '16:18', bot: 'BOT-005', label: 'HALTED', tone: 'red' as Tone, text: 'Risk limit reached. Bot halted' },
  { time: '16:15', bot: 'BOT-001', label: 'CLOSED POSITION', tone: 'cyan' as Tone, text: 'Take profit hit. +$118.47' },
  { time: '16:12', bot: 'BOT-002', label: 'FOUND SETUP', tone: 'violet' as Tone, text: 'ETHUSDT mean reversion signal detected' },
  { time: '16:05', bot: 'BOT-004', label: 'CLOSED POSITION', tone: 'red' as Tone, text: 'Stop loss hit. -$36.21' },
]

const navItems = [
  { id: 'operations', label: 'Operations', icon: LayoutDashboard },
  { id: 'bots', label: 'Bots', icon: Bot },
  { id: 'strategies', label: 'Strategies', icon: Radar },
  { id: 'markets', label: 'Markets', icon: LineChart },
  { id: 'analytics', label: 'Analytics', icon: ChartNoAxesCombined },
  { id: 'risk', label: 'Risk', icon: ShieldAlert },
  { id: 'reports', label: 'Reports', icon: Terminal },
  { id: 'settings', label: 'Settings', icon: Settings2 },
]

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

function PageWorkspace({ page, botsOnline, onSelect }: { page: string; botsOnline: number; onSelect: (bot: DeskBot) => void }) {
  const title = navItems.find((item) => item.id === page)?.label ?? 'Operations'
  if (page === 'operations') return null
  return <section className="workspace-panel">
    <div className="workspace-heading"><div><span className="section-kicker">ALGODESK / WORKSPACE</span><h2>{title}</h2><p>Superfície de controlo conectada ao motor paper trading.</p></div><button className="ghost-button"><RefreshCw size={15} /> Atualizar dados</button></div>
    <div className="workspace-grid">
      {page === 'bots' && bots.map((bot) => <button className="workspace-row" key={bot.id} onClick={() => onSelect(bot)}><BotAvatar status={bot.status} tone={bot.tone} /><div><strong>{bot.id}</strong><span>{bot.symbol} · {bot.strategy}</span></div><span className={`status-chip ${toneClass(bot.tone)}`}>{bot.status}</span><b>{bot.pnl}</b><ChevronRight size={16} /></button>)}
      {page !== 'bots' && <>
        <div className="detail-panel"><div className="panel-heading"><span>System overview</span><StatusMark tone="cyan" pulse /></div><h3>{title === 'Risk' ? 'Risk Engine armed' : `${title} is ready`}</h3><p>Dados demonstrativos em tempo real para validar a operação antes de conectar credenciais da Binance.</p><div className="progress-track"><span style={{ width: `${page === 'Risk' ? 68 : 84}%` }} /></div><small>{page === 'Risk' ? '68% of risk budget available' : `${botsOnline}/5 bot processes healthy`}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Equity telemetry</span><span className="positive">+2.83%</span></div><Sparkline /><div className="chart-axis"><span>09:00</span><span>12:00</span><span>16:30</span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Guardrails</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="cyan" /><span>Live trading locked</span><b>ON</b></div><div className="guardrail"><StatusMark tone="amber" /><span>Paper mode</span><b>ACTIVE</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Spot only</span><b>ON</b></div></div>
      </>}
    </div>
  </section>
}

function App() {
  const [activePage, setActivePage] = useState('operations')
  const [selectedBot, setSelectedBot] = useState<DeskBot | null>(null)
  const [search, setSearch] = useState('')
  const [hardStopped, setHardStopped] = useState(false)
  const [enableText, setEnableText] = useState('')
  const [notice, setNotice] = useState('')
  const [clock, setClock] = useState(new Date())

  useEffect(() => { const timer = window.setInterval(() => setClock(new Date()), 1000); return () => window.clearInterval(timer) }, [])
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(''), 3600); return () => window.clearTimeout(timer) }, [notice])

  const visibleBots = useMemo(() => bots.filter((bot) => `${bot.id} ${bot.symbol} ${bot.strategy} ${bot.status}`.toLowerCase().includes(search.toLowerCase())), [search])
  const botsOnline = bots.filter((bot) => bot.status !== 'HALTED').length
  const currentTime = clock.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const selectBot = (bot: DeskBot) => { setSelectedBot(bot); setNotice(`${bot.id} selecionado para inspeção`) }
  const stopAll = () => { setHardStopped(true); setNotice('HARD STOP ativado · novas ordens bloqueadas') }
  const reenable = () => { if (enableText.trim() === 'ENABLE') { setHardStopped(false); setEnableText(''); setNotice('Motor reativado em modo PAPER') } else setNotice('Digite ENABLE para reativar o motor') }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><span /><span /><span /></div>
      <div className="brand-word">ALG<span>O</span></div>
      <div className="nav-list">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => setActivePage(id)}><Icon size={19} strokeWidth={1.7} /><span>{label}</span></button>)}</div>
      <div className="sidebar-bottom"><div className="side-divider" /><button className="nav-item"><Network size={18} /><span>Connect</span></button><span className="version">v0.1.0 · PAPER</span></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumb"><span>ALGODESK</span><ChevronRight size={14} /><b>{navItems.find((item) => item.id === activePage)?.label.toUpperCase()}</b></div><div className="top-actions"><span className="connection"><StatusMark tone="cyan" pulse /> Binance connected</span><span className="top-time">{currentTime} BRT</span><button className="icon-button" aria-label="Notificações"><Bell size={17} /></button><button className="avatar-user">AD</button><span className="user-name">AlgoTrader</span></div></header>

      <div className="content">
        <div className="page-heading"><div><p className="section-kicker">TRADING CONTROL ROOM · BINANCE SPOT</p><h1>{activePage === 'operations' ? 'Operations Desk' : navItems.find((item) => item.id === activePage)?.label}</h1><p className="heading-sub">{activePage === 'operations' ? 'Five bots. One mission. Disciplined execution.' : 'Observe, validate and keep every decision inside the guardrails.'}</p></div><div className="heading-controls"><div className="search-box"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find a bot..." aria-label="Buscar bot" /></div><div className="mode-select"><span className="mode-dot" />PAPER<ChevronRight size={14} /></div></div></div>
        <div className="stats-row"><StatCard label="Equity" value="$ 12,428.50" detail="+2.40% since open" icon={WalletCards} /><StatCard label="Daily PnL" value="$ 342.18" detail="+2.83% today" tone="cyan" icon={CircleDollarSign} /><StatCard label="Drawdown" value="-3.12%" detail="Hard limit · 5.00%" tone="red" icon={Gauge} /><StatCard label="Bots online" value={`${botsOnline} / 5`} detail="1 bot halted" tone="amber" icon={Bot} /><button className={`stop-button ${hardStopped ? 'is-stopped' : ''}`} onClick={hardStopped ? () => setHardStopped(false) : stopAll}><Square size={17} fill="currentColor" />{hardStopped ? 'HARD STOP ACTIVE' : 'PARAR TODOS OS ROBÔS'}</button></div>

        <PageWorkspace page={activePage} botsOnline={botsOnline} onSelect={selectBot} />
        {activePage === 'operations' && <div className="operations-grid">
          <section className="desk-panel"><div className="desk-panel-header"><div><span className="panel-eyebrow"><Radio size={13} /> LIVE SIMULATION</span><h2>Trading floor</h2></div><div className="desk-legend"><span><i className="legend-dot cyan" />Open</span><span><i className="legend-dot violet" />Scanning</span><span><i className="legend-dot amber" />Waiting</span><span><i className="legend-dot red" />Halted</span></div></div>
            <div className="trading-floor"><div className="floor-back-wall"><div className="wall-screen screen-map"><span>MARKET GRID</span><div className="world-dots" /></div><div className="wall-screen screen-chart"><span>BTC / ETH</span><Sparkline /></div><div className="wall-copy">DISCIPLINE<br /><em>BEATS</em><br />EMOTION</div></div><div className="floor-grid" /><div className="floor-light light-one" /><div className="floor-light light-two" />{visibleBots.map((bot, index) => <DeskStation bot={bot} index={index} key={bot.id} onSelect={() => selectBot(bot)} selected={selectedBot?.id === bot.id} />)}<div className="floor-label">ALGODESK <span>///</span> PAPER CONTROL FLOOR</div></div>
          </section>
          <aside className="activity-panel"><div className="activity-header"><div><span className="panel-eyebrow"><Activity size={13} /> SYSTEM LOG</span><h2>Activity feed</h2></div><button className="filter-button">All bots <ChevronRight size={13} /></button></div><div className="activity-list">{activities.map((item, index) => <button className="activity-item" key={`${item.time}-${index}`} onClick={() => { const bot = bots.find((candidate) => candidate.id === item.bot); if (bot) selectBot(bot) }}><div className="activity-rail"><StatusMark tone={item.tone} pulse={index === 0} /><span /></div><div className="activity-copy"><div className="activity-meta"><time>{item.time}</time><strong>{item.bot}</strong><em className={toneClass(item.tone)}>{item.label}</em></div><p>{item.text}</p></div></button>)}</div><button className="view-all">View full event log <ChevronRight size={14} /></button></aside>
        </div>}

        <footer className="bottom-strip"><div className="allocation"><span className="strip-label">PORTFOLIO ALLOCATION</span><div className="allocation-body"><div className="donut"><span>100%</span></div><div className="allocation-keys"><span><i className="legend-dot cyan" />BTCUSDT <b>48%</b></span><span><i className="legend-dot violet" />ETHUSDT <b>32%</b></span><span><i className="legend-dot sky" />Others <b>20%</b></span></div></div></div><div className="strip-stat"><span className="strip-label">OPEN POSITIONS</span><strong>2</strong><small>Across 4 active bots</small></div><div className="strip-stat positive-stat"><span className="strip-label">REALIZED PNL · 24H</span><strong>+$ 298.65</strong><small>12 trades</small></div><div className="strip-stat"><span className="strip-label">WIN RATE · 24H</span><strong>75%</strong><small>9 W / 3 L</small></div><div className="strip-stat"><span className="strip-label">AVG. TRADE DURATION</span><strong>1h 24m</strong><small>Paper execution</small></div><div className="system-status"><span className="strip-label">SYSTEM STATUS</span><div><StatusMark tone="cyan" /> Binance connected</div><div><StatusMark tone="cyan" /> Market data live</div><div><StatusMark tone="cyan" /> Bots engine running</div></div><div className="strip-pulse"><Sparkline /><span>STABLE</span></div></footer>
      </div>
    </main>

    {selectedBot && <div className="inspector"><div className="inspector-top"><span>BOT INSPECTOR</span><button onClick={() => setSelectedBot(null)} aria-label="Fechar inspetor"><X size={15} /></button></div><div className="inspector-hero"><BotAvatar status={selectedBot.status} tone={selectedBot.tone} /><div><strong>{selectedBot.id}</strong><span>{selectedBot.strategy}</span></div></div><div className="inspector-status"><StatusMark tone={selectedBot.tone} pulse={selectedBot.status === 'SCANNING'} /><b>{selectedBot.status}</b><span>• {selectedBot.position}</span></div><div className="inspector-grid"><div><small>SYMBOL</small><b>{selectedBot.symbol}</b></div><div><small>PnL</small><b className={selectedBot.tone === 'red' ? 'negative' : 'positive'}>{selectedBot.pnl}</b></div><div><small>TIMEFRAME</small><b>1H</b></div><div><small>RISK USED</small><b>0.25%</b></div></div><div className="inspector-chart"><span>POSITION TELEMETRY</span><Sparkline /></div><p className="inspector-note">{selectedBot.activity}</p><button className="inspector-action" onClick={() => setNotice(`${selectedBot.id}: ação manual bloqueada no modo PAPER`)}><SlidersHorizontal size={15} /> View strategy config</button></div>}

    {hardStopped && <div className="stop-modal-backdrop"><div className="stop-modal"><div className="modal-icon"><ShieldAlert size={22} /></div><span className="section-kicker">SAFETY INTERLOCK</span><h2>Hard stop active</h2><p>Novas ordens e ordens pendentes estão bloqueadas. Para reativar o motor PAPER, digite <strong>ENABLE</strong>.</p><input value={enableText} onChange={(event) => setEnableText(event.target.value)} placeholder="Digite ENABLE" autoFocus /><div className="modal-actions"><button className="ghost-button" onClick={() => { setHardStopped(false); setEnableText('') }}>Keep stopped</button><button className="primary-button" onClick={reenable}>Re-enable engine <Zap size={15} /></button></div></div></div>}
    {notice && <div className="toast"><StatusMark tone="cyan" />{notice}</div>}
  </div>
}

export default App
