'use client'

import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity, Bell, Bot, ChartNoAxesCombined, ChevronRight, CircleDollarSign,
  Gauge, LayoutDashboard, LockKeyhole, Network, Radio,
  RefreshCw, Search, Settings2, ShieldAlert, SlidersHorizontal, Square,
  WalletCards, X, Zap,
} from 'lucide-react'
import { Line, LineChart, ResponsiveContainer } from 'recharts'
import { Button } from './components/ui/button'

type BotStatus = 'POSITION OPEN' | 'SCANNING' | 'WAITING' | 'HALTED' | 'NOT DEPLOYED'
type Tone = 'cyan' | 'violet' | 'amber' | 'red'
type FeedStatus = 'websocket' | 'rest' | 'offline'
type AccountStatus = 'loading' | 'connected' | 'not-configured' | 'error'
type AccountSummary = {
  configured: boolean
  connected: boolean
  mode?: string
  symbol?: string
  base_asset?: string
  quote_asset?: string
  base_total?: number
  quote_total?: number
  mark_price?: number
  account_value_quote?: number
  wallet_value_quote?: number
  wallet_asset_count?: number
  wallet_valuation_complete?: boolean
  wallet_assets?: Array<{
    asset: string
    total: number
    value_quote?: number | null
  }>
}
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
  spread: number
  exposure_percent: number
  max_exposure_percent: number
  sharpe: number
  sortino: number
  average_win: number
  average_loss: number
  expectancy: number
  recovery_factor: number
  buy_hold_return_percent: number
  partial_fills: number
  stop_loss_trades: number
  take_profit_trades: number
  latency_bars: number
}
type BacktestMeta = {
  data_points: number
  data_start: string
  data_end: string
  lookahead: boolean
  frictions?: {
    fee_bps: number
    slippage_bps: number
    spread_bps: number
    latency_bars: number
    partial_fill_ratio: number
    filters_from_exchange_info: boolean
  }
}
type BacktestSplit = {
  name: string
  data_points: number
  metrics: { return_percent: number; max_drawdown_percent: number; trades: number }
  lookahead: boolean
}
type WalkForwardFold = {
  fold: number
  selected: { fast_period: number; slow_period: number }
  out_of_sample: { metrics: { return_percent: number; max_drawdown_percent: number; trades: number } }
}
type PaperSummary = {
  source?: string
  mode?: string
  status?: string
  symbol?: string
  interval?: string
  equity: number
  starting_equity?: number
  daily_pnl: number
  unrealized_pnl?: number
  total_pnl?: number
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
type EquityPoint = { captured_at: string; equity: number }

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

function formatAsset(value: number | null | undefined, maximumFractionDigits = 8) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits })
}

function formatWalletAssets(account: AccountSummary | null) {
  if (!account?.wallet_assets?.length) return account?.connected ? 'Nenhum ativo com saldo' : 'Consultando Binance'
  const visible = account.wallet_assets.slice(0, 2).map((asset) => `${formatAsset(asset.total)} ${asset.asset}`)
  const remaining = account.wallet_assets.length - visible.length
  return `${visible.join(' · ')}${remaining > 0 ? ` · +${remaining} ativos` : ''}`
}

function buildDeskBots(summary: PaperSummary | null, hardStopped: boolean): DeskBot[] {
  const modeLabel = summary?.mode?.toUpperCase() ?? 'PAPER'
  const engineLabel = `${modeLabel} engine`
  const engineRunning = summary?.status === 'running'
  const runtimeIssue = summary?.last_error?.trim()
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
        ? `${engineLabel} interlocked by the local safety control.`
        : runtimeIssue
          ? `${engineLabel} paused: ${runtimeIssue}`
        : engineRunning
          ? `Live ${engineLabel.toLowerCase()} on ${activeSymbol} using closed ${summary?.interval ?? '1h'} candles.`
          : `Waiting for the ${engineLabel.toLowerCase()} to report a healthy Binance cycle.`,
    }
    : {
      ...template,
      status: 'NOT DEPLOYED',
      pnl: '—',
      pnlPct: '—',
      position: 'FLAT',
      activity: `Configured visual station only; no ${modeLabel.toLowerCase()} runtime is deployed for this strategy.`,
    })
}

const navItems = [
  { id: 'operations', label: 'Operações', path: '/desk', icon: LayoutDashboard },
  { id: 'bots', label: 'Robôs', path: '/bots', icon: Bot },
  { id: 'trades', label: 'Entradas e saídas', path: '/trades', icon: Activity },
  { id: 'backtests', label: 'Backtests', path: '/backtests', icon: ChartNoAxesCombined },
  { id: 'risk', label: 'Risco', path: '/risk', icon: ShieldAlert },
  { id: 'system', label: 'Sistema', path: '/system', icon: Network },
  { id: 'settings', label: 'Configurações', path: '/settings', icon: Settings2 },
]

function pageForPath(pathname: string) {
  return navItems.find((item) => item.path === pathname)?.id ?? 'operations'
}

function runtimeApiUrl() {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim()
  if (configured) return configured.replace(/\/$/, '')
  if (typeof window !== 'undefined') {
    const localDevPort = window.location.port === '3000' || window.location.port === '4173'
    if (localDevPort) return `${window.location.protocol}//${window.location.hostname}:8000`
    return window.location.origin
  }
  return 'http://localhost:8000'
}

function toneClass(tone: Tone) { return `tone-${tone}` }

function StatusMark({ tone, pulse = false }: { tone: Tone; pulse?: boolean }) {
  return <span className={`status-mark ${toneClass(tone)} ${pulse ? 'is-pulsing' : ''}`} />
}

function BotAvatar({ status, tone }: { status: BotStatus; tone: Tone }) {
  return (
    <motion.div className={`bot-avatar ${toneClass(tone)} state-${status.toLowerCase().replaceAll(' ', '-')}`} animate={status === 'SCANNING' ? { y: [0, -2, 0] } : { y: 0 }} transition={{ duration: 2, repeat: status === 'SCANNING' ? Infinity : 0, ease: 'easeInOut' }}>
      <div className="avatar-shadow" />
      <div className="avatar-body"><div className="avatar-chest-line" /></div>
      <div className="avatar-head"><div className="avatar-visor"><span /><span /></div><div className="avatar-ear left" /><div className="avatar-ear right" /></div>
      {status === 'SCANNING' && <div className="scan-beam" />}
    </motion.div>
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

function Sparkline({ values, label = 'Telemetry sparkline' }: { values?: number[]; label?: string }) {
  const cleanValues = values?.filter((value) => Number.isFinite(value)) ?? []
  const minimum = cleanValues.length ? Math.min(...cleanValues) : 0
  const maximum = cleanValues.length ? Math.max(...cleanValues) : 0
  const spread = maximum - minimum || 1
  const coordinates = cleanValues.map((value, index) => {
    const x = cleanValues.length > 1 ? index / (cleanValues.length - 1) * 180 : 90
    const y = 38 - ((value - minimum) / spread * 30)
    return `${x.toFixed(2)} ${y.toFixed(2)}`
  })
  const path = coordinates.length > 1 ? `M${coordinates.join(' L')}` : 'M0 30 L180 30'
  const areaPath = coordinates.length > 1 ? `${path} L180 44 L0 44Z` : 'M0 30 L180 30 L180 44 L0 44Z'
  return <svg className="sparkline" viewBox="0 0 180 44" preserveAspectRatio="none" aria-label={label}><path d={path} fill="none" stroke="currentColor" strokeWidth="2" /><path d={areaPath} fill="currentColor" opacity=".08" /></svg>
}

function EquityChart({ values }: { values: number[] }) {
  const data = values.filter((value) => Number.isFinite(value)).map((equity, index) => ({ equity, index }))
  if (data.length < 2) return <Sparkline values={values} label="Persisted paper equity" />
  return <div style={{ width: '100%', height: 44 }}><ResponsiveContainer width="100%" height="100%"><LineChart data={data}><Line type="monotone" dataKey="equity" stroke="currentColor" strokeWidth={2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
}

function StatCard({ label, value, detail, tone = 'cyan', icon: Icon }: { label: string; value: string; detail: string; tone?: Tone; icon: typeof Activity }) {
  return <div className={`stat-card ${toneClass(tone)}`}><div className="stat-header"><span>{label}</span><Icon size={16} /></div><strong>{value}</strong><small>{detail}</small></div>
}

function PageWorkspace({ page, bots, botsOnline, onSelect, backtest, backtestMeta, backtestState, backtestSplits, parameterSweepCount, walkForwardFolds, paperSummary, systemMetrics, riskConfig, equityPoints, paperActivities }: { page: string; bots: DeskBot[]; botsOnline: number; onSelect: (bot: DeskBot) => void; backtest: BacktestMetrics | null; backtestMeta: BacktestMeta | null; backtestState: 'loading' | 'ready' | 'error'; backtestSplits: BacktestSplit[]; parameterSweepCount: number; walkForwardFolds: WalkForwardFold[]; paperSummary: PaperSummary | null; systemMetrics: SystemMetrics | null; riskConfig: RiskConfig | null; equityPoints: EquityPoint[]; paperActivities: PaperActivity[] }) {
  const title = navItems.find((item) => item.id === page)?.label ?? 'Operações'
  const modeLabel = paperSummary?.mode?.toUpperCase() ?? 'PAPER'
  const engineLabel = `${modeLabel} engine`
  const paperRunning = paperSummary?.status === 'running'
  const drawdown = Math.abs(paperSummary?.drawdown_percent ?? 0)
  const drawdownLimit = riskConfig?.hard_drawdown_limit_percent ?? 5
  const riskBudgetUsed = drawdownLimit ? Math.min(100, drawdown / drawdownLimit * 100) : 0
  const dataHealthy = Boolean(systemMetrics?.database_connected && paperRunning)
  if (page === 'operations') return null
  return <section className="workspace-panel">
    <div className="workspace-heading"><div><span className="section-kicker">ALGODESK / WORKSPACE</span><h2>{title}</h2><p>Superfície de controlo conectada ao {engineLabel.toLowerCase()}.</p></div><Button variant="ghost" className="ghost-button" onClick={() => window.location.reload()}><RefreshCw size={15} /> Atualizar dados</Button></div>
    <div className="workspace-grid">
      {page === 'bots' && bots.map((bot) => <button className="workspace-row" key={bot.id} onClick={() => onSelect(bot)}><BotAvatar status={bot.status} tone={bot.tone} /><div><strong>{bot.id}</strong><span>{bot.symbol} · {bot.strategy}</span></div><span className={`status-chip ${toneClass(bot.tone)}`}>{bot.status}</span><b>{bot.pnl}</b><ChevronRight size={16} /></button>)}
      {page === 'backtests' && <>
        <div className="detail-panel"><div className="panel-heading"><span>Backtest histórico da Binance</span><StatusMark tone={backtestState === 'error' ? 'amber' : 'violet'} pulse={backtestState === 'loading'} /></div><h3>{backtest ? `${backtest.return_percent >= 0 ? '+' : ''}${backtest.return_percent.toFixed(2)}% de retorno` : backtestState === 'error' ? 'Dados de pesquisa indisponíveis' : 'Carregando histórico da Binance'}</h3><p>{backtestMeta ? `${backtestMeta.data_points} candles BTCUSDT fechados · ${backtestMeta.data_start.slice(0, 10)} → ${backtestMeta.data_end.slice(0, 10)}` : backtestState === 'error' ? 'A solicitação histórica à Binance falhou; nenhum resultado sintético é exibido.' : 'Buscando candles fechados da Binance Spot.'}</p><div className="progress-track"><span style={{ width: `${Math.min(100, Math.max(0, backtest?.win_rate_percent ?? 0))}%` }} /></div><small>{backtest ? `${backtest.trades} operações concluídas · ${backtest.win_rate_percent.toFixed(0)}% de acerto` : backtestState === 'error' ? 'Aguardando uma resposta saudável dos dados de mercado' : 'Aguardando a API'}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Métricas da pesquisa</span><span className="positive">{backtest ? `$${backtest.equity.toFixed(2)}` : '—'}</span></div><div className="metric-list"><span>Drawdown máximo <b>{backtest ? `${backtest.max_drawdown_percent.toFixed(2)}%` : '—'}</b></span><span>Fator de lucro <b>{backtest ? backtest.profit_factor === null ? '—' : backtest.profit_factor.toFixed(2) : '—'}</b></span><span>Tempo exposto <b>{backtest ? `${backtest.exposure_percent.toFixed(1)}%` : '—'}</b></span><span>Exposição máxima <b>{backtest ? `${backtest.max_exposure_percent.toFixed(1)}%` : '—'}</b></span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Custos de negociação</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="amber" /><span>Taxas</span><b>{backtest ? `$${backtest.fees.toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="amber" /><span>Deslizamento / spread</span><b>{backtest ? `$${(backtest.slippage + backtest.spread).toFixed(2)}` : '—'}</b></div><div className="guardrail"><StatusMark tone="violet" /><span>Latência / execução parcial</span><b>{backtest ? `${backtest.latency_bars} barra · ${backtest.partial_fills}` : '—'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Antevisão indevida</span><b>DESLIGADA</b></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Desempenho</span><span className="positive">{backtest ? `${backtest.cagr_percent.toFixed(2)}% CAGR` : '—'}</span></div><div className="metric-list"><span>Sharpe <b>{backtest ? backtest.sharpe.toFixed(2) : '—'}</b></span><span>Sortino <b>{backtest ? backtest.sortino.toFixed(2) : '—'}</b></span><span>Comprar e manter <b>{backtest ? `${backtest.buy_hold_return_percent.toFixed(2)}%` : '—'}</b></span></div></div>
        <div className="detail-panel split-panel"><div className="panel-heading"><span>Divisões de validação</span><span>{backtestSplits.length}/3</span></div>{backtestSplits.length ? backtestSplits.map((split) => <div className="guardrail" key={split.name}><StatusMark tone={split.name === 'out_of_sample' ? 'amber' : 'cyan'} /><span>{split.name.replace('in_sample', 'amostra').replace('out_of_sample', 'fora da amostra').replaceAll('_', ' ')}</span><b>{split.metrics.return_percent.toFixed(2)}% · {split.metrics.trades} operações</b></div>) : <p>Aguardando resultados independentes de amostra, validação e fora da amostra.</p>}<small>Variações EMA vizinhas: {parameterSweepCount || '—'} · sem ajuste no OOS</small></div>
        <div className="detail-panel split-panel"><div className="panel-heading"><span>Walk-forward fora da amostra</span><span>{walkForwardFolds.length} etapa{walkForwardFolds.length === 1 ? '' : 's'}</span></div>{walkForwardFolds.length ? walkForwardFolds.map((fold) => <div className="guardrail" key={fold.fold}><StatusMark tone="violet" /><span>EMA {fold.selected.fast_period}/{fold.selected.slow_period}</span><b>{fold.out_of_sample.metrics.return_percent.toFixed(2)}% · {fold.out_of_sample.metrics.trades} operações</b></div>) : <p>A validação independente e as janelas OOS intocadas precisam de mais candles fechados.</p>}<small>Os parâmetros são escolhidos apenas na validação; o OOS é calculado depois.</small></div>
      </>}
      {page === 'trades' && <div className="detail-panel split-panel"><div className="panel-heading"><span>{modeLabel} event log</span><span>{paperActivities.length} events</span></div>{paperActivities.length ? paperActivities.map((activity, index) => <div className="guardrail" key={`${activity.time}-${index}`}><StatusMark tone={activity.tone} /><span>{activity.time} · {activity.bot}</span><b>{activity.label}</b><small>{activity.text}</small></div>) : <p>No persisted {modeLabel.toLowerCase()} events are available yet. The worker only records activity after a closed-candle cycle.</p>}<small>Source: persisted {engineLabel} events from Binance closed candles.</small></div>}
      {page === 'settings' && <>
        <div className="detail-panel"><div className="panel-heading"><span>Modo de execução</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="cyan" /><span>Modo de negociação</span><b>{paperSummary?.mode?.toUpperCase() ?? 'PAPER'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Negociação ao vivo</span><b>BLOQUEADA</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Fonte de mercado</span><b>BINANCE SPOT</b></div><small>As chaves ficam somente no servidor e nunca são expostas neste painel.</small></div>
        <div className="detail-panel"><div className="panel-heading"><span>Perfil da estratégia</span><StatusMark tone="violet" /></div><div className="metric-list"><span>Estratégia <b>Tendência EMA</b></span><span>Ativo <b>{paperSummary?.symbol ?? 'BTCUSDT'}</b></span><span>Intervalo <b>{paperSummary?.interval ?? '1h'}</b></span><span>Worker <b>{paperSummary?.status?.toUpperCase() ?? 'INICIANDO'}</b></span></div></div>
      </>}
      {page !== 'bots' && page !== 'backtests' && page !== 'trades' && page !== 'settings' && <>
        <div className="detail-panel"><div className="panel-heading"><span>System overview</span><StatusMark tone={dataHealthy ? 'cyan' : 'amber'} pulse={dataHealthy} /></div><h3>{title === 'Risk' ? (paperRunning ? 'Risk Engine armed' : 'Risk telemetry waiting') : title === 'System' ? (systemMetrics?.database_connected ? 'System healthy' : 'System unavailable') : title === 'Trades' ? `${paperSummary?.trades_24h ?? 0} closed ${modeLabel.toLowerCase()} trades` : `${title} is ready`}</h3><p>{title === 'Risk' ? `Risk is evaluated before each ${modeLabel.toLowerCase()} intent; no live order path is enabled.` : title === 'System' ? 'Runtime health comes from the FastAPI readiness and metrics endpoints.' : title === 'Trades' ? `The list is backed by the ${engineLabel.toLowerCase()} events generated from closed Binance candles.` : 'Public Binance market data is live; account data remains read-only and optional.'}</p><div className="progress-track"><span style={{ width: `${title === 'Risk' ? riskBudgetUsed : dataHealthy ? 100 : 0}%` }} /></div><small>{title === 'Risk' ? `${drawdown.toFixed(2)}% drawdown used · limit ${drawdownLimit.toFixed(2)}%` : title === 'System' ? `${systemMetrics?.websocket_connections ?? 0} market stream connection(s) · ${systemMetrics?.websocket_reconnects ?? 0} reconnect(s)` : `${botsOnline}/5 visual stations backed by a deployed ${modeLabel.toLowerCase()} engine`}</small></div>
        <div className="detail-panel chart-detail"><div className="panel-heading"><span>Equity telemetry</span><span className={paperSummary && paperSummary.daily_pnl >= 0 ? 'positive' : 'negative'}>{paperSummary ? formatSignedUsd(paperSummary.daily_pnl) : '—'}</span></div><EquityChart values={equityPoints.map((point) => point.equity)} /><div className="chart-axis"><span>Paper start</span><span>{paperSummary?.last_candle_at ? new Date(paperSummary.last_candle_at).toLocaleDateString('pt-BR') : '—'}</span><span>{paperSummary?.last_run_at ? new Date(paperSummary.last_run_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}</span></div></div>
        <div className="detail-panel"><div className="panel-heading"><span>Proteções</span><LockKeyhole size={15} /></div><div className="guardrail"><StatusMark tone="cyan" /><span>Negociação ao vivo bloqueada</span><b>ATIVA</b></div><div className="guardrail"><StatusMark tone={paperRunning ? 'amber' : 'red'} /><span>Modo {modeLabel}</span><b>{paperRunning ? 'ATIVO' : 'AGUARDANDO'}</b></div><div className="guardrail"><StatusMark tone="cyan" /><span>Apenas Spot</span><b>ATIVO</b></div></div>
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
  // Keep the server and first client render identical; the real clock starts
  // after hydration to avoid a React hydration mismatch in the live dashboard.
  const [clock, setClock] = useState<Date | null>(null)
  const [livePrices, setLivePrices] = useState<Record<string, number>>({})
  const [feedStatus, setFeedStatus] = useState<FeedStatus>('offline')
  const [accountStatus, setAccountStatus] = useState<AccountStatus>('loading')
  const [accountSummary, setAccountSummary] = useState<AccountSummary | null>(null)
  const [backtestMetrics, setBacktestMetrics] = useState<BacktestMetrics | null>(null)
  const [backtestMeta, setBacktestMeta] = useState<BacktestMeta | null>(null)
  const [backtestSplits, setBacktestSplits] = useState<BacktestSplit[]>([])
  const [parameterSweepCount, setParameterSweepCount] = useState(0)
  const [walkForwardFolds, setWalkForwardFolds] = useState<WalkForwardFold[]>([])
  const [backtestState, setBacktestState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [paperSummary, setPaperSummary] = useState<PaperSummary | null>(null)
  const [paperActivities, setPaperActivities] = useState<PaperActivity[]>([])
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null)
  const [riskConfig, setRiskConfig] = useState<RiskConfig | null>(null)
  const [equityPoints, setEquityPoints] = useState<EquityPoint[]>([])

  useEffect(() => {
    setActivePage(pageForPath(window.location.pathname))
    setClock(new Date())
    const timer = window.setInterval(() => setClock(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const onPopState = () => setActivePage(pageForPath(window.location.pathname))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    const loadEquity = () => fetch(`${apiUrl}/api/paper/equity?limit=60`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { points?: EquityPoint[] } : Promise.reject(new Error('equity request failed')))
      .then((payload) => setEquityPoints((payload.points ?? []).filter((point) => Number.isFinite(point.equity))))
      .catch(() => setEquityPoints([]))
    void loadEquity()
    const timer = window.setInterval(loadEquity, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => { if (!notice) return; const timer = window.setTimeout(() => setNotice(''), 3600); return () => window.clearTimeout(timer) }, [notice])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL?.trim() || apiUrl.replace(/^http/, 'ws')
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
    const apiUrl = runtimeApiUrl()
    const loadAccount = () => fetch(`${apiUrl}/api/account/summary`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as AccountSummary : Promise.reject(new Error('account request failed')))
      .then((payload) => {
        setAccountSummary(payload)
        setAccountStatus(payload.connected ? 'connected' : payload.configured ? 'error' : 'not-configured')
      })
      .catch(() => { setAccountSummary(null); setAccountStatus('error') })
    void loadAccount()
    const timer = window.setInterval(loadAccount, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    fetch(`${apiUrl}/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=500`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { metrics?: BacktestMetrics; data_points?: number; data_start?: string; data_end?: string; lookahead?: boolean; frictions?: BacktestMeta['frictions']; splits?: BacktestSplit[]; parameter_sweep?: unknown[]; walk_forward?: { folds?: WalkForwardFold[] } } : Promise.reject(new Error('backtest request failed')))
      .then((payload) => {
        setBacktestMetrics(payload.metrics ?? null)
        setBacktestMeta(payload.data_points && payload.data_start && payload.data_end ? { data_points: payload.data_points, data_start: payload.data_start, data_end: payload.data_end, lookahead: payload.lookahead ?? false, frictions: payload.frictions } : null)
        setBacktestSplits(payload.splits ?? [])
        setParameterSweepCount(payload.parameter_sweep?.length ?? 0)
        setWalkForwardFolds(payload.walk_forward?.folds ?? [])
        setBacktestState(payload.metrics ? 'ready' : 'error')
      })
      .catch(() => { setBacktestMetrics(null); setBacktestMeta(null); setBacktestSplits([]); setParameterSweepCount(0); setWalkForwardFolds([]); setBacktestState('error') })
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    const loadPaper = () => fetch(`${apiUrl}/api/paper/summary`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as PaperSummary : Promise.reject(new Error('paper summary request failed')))
      .then((payload) => { setPaperSummary(payload); setHardStopped(payload.hard_stop ?? false) })
      .catch(() => setPaperSummary(null))
    void loadPaper()
    const timer = window.setInterval(loadPaper, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    const loadEvents = () => fetch(`${apiUrl}/api/paper/events`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { events?: PaperActivity[] } : Promise.reject(new Error('paper events request failed')))
      .then((payload) => setPaperActivities(payload.events ?? []))
      .catch(() => setPaperActivities([]))
    void loadEvents()
    const timer = window.setInterval(loadEvents, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    const loadSystemMetrics = () => fetch(`${apiUrl}/api/system/metrics`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as SystemMetrics : Promise.reject(new Error('system metrics request failed')))
      .then((payload) => setSystemMetrics(payload))
      .catch(() => setSystemMetrics(null))
    void loadSystemMetrics()
    const timer = window.setInterval(loadSystemMetrics, 15000)
    return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    const apiUrl = runtimeApiUrl()
    fetch(`${apiUrl}/api/risk`, { cache: 'no-store' })
      .then(async (response) => response.ok ? await response.json() as { config?: RiskConfig } : Promise.reject(new Error('risk request failed')))
      .then((payload) => setRiskConfig(payload.config ?? null))
      .catch(() => setRiskConfig(null))
  }, [])

  const bots = useMemo(() => buildDeskBots(paperSummary, hardStopped), [paperSummary, hardStopped])
  const visibleBots = useMemo(() => bots.filter((bot) => `${bot.id} ${bot.symbol} ${bot.strategy} ${bot.status}`.toLowerCase().includes(search.toLowerCase())), [bots, search])
  const botsOnline = paperSummary?.status === 'running' ? paperSummary.bot_count : 0
  const modeLabel = paperSummary?.mode?.toUpperCase() ?? 'PAPER'
  const engineLabel = `${modeLabel} engine`
  const currentTime = clock?.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) ?? '--:--:--'
  const runtimeIssue = paperSummary?.last_error?.trim()
  const displayActivities: PaperActivity[] = paperActivities.length ? paperActivities : [{ time: '—', bot: modeLabel, label: runtimeIssue || paperSummary?.status === 'error' ? 'PAUSADO' : 'AGUARDANDO', tone: runtimeIssue || paperSummary?.status === 'error' ? 'red' : 'amber', text: runtimeIssue ?? (paperSummary?.status === 'error' ? `${engineLabel} indisponível` : 'Aguardando o primeiro sinal de candle fechado') }]
  const engineHeadline = paperSummary?.status === 'running' ? `${engineLabel} ativo` : `${engineLabel} protegido e aguardando validação`

  const selectBot = (bot: DeskBot) => { setSelectedBot(bot); setNotice(`${bot.id} selecionado para inspeção`) }
  const navigate = (page: string) => {
    const item = navItems.find((candidate) => candidate.id === page)
    if (!item) return
    window.history.pushState({}, '', item.path)
    setActivePage(page)
  }
  const setPaperKillSwitch = async (enabled: boolean, confirmation?: string) => {
    const apiUrl = runtimeApiUrl()
    try {
      const response = await fetch(`${apiUrl}/api/paper/kill-switch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, confirmation }) })
      if (!response.ok) throw new Error((await response.json() as { detail?: string }).detail ?? 'kill switch request failed')
      const payload = await response.json() as { paper?: PaperSummary }
      setPaperSummary(payload.paper ?? null)
      setHardStopped(enabled)
      setNotice(enabled ? `HARD STOP ativado no ${engineLabel.toLowerCase()}` : `${engineLabel} reativado`)
      if (!enabled) { setEnableText(''); }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Não foi possível atualizar o HARD STOP')
      if (enabled) setHardStopped(false)
    }
  }
  const stopAll = () => { setHardStopped(true); void setPaperKillSwitch(true) }
  const reenable = () => {
    if (runtimeIssue) {
      setNotice('O motor continua pausado até a validação da conta Testnet')
      return
    }
    if (enableText.trim() === 'ENABLE') void setPaperKillSwitch(false, 'ENABLE'); else setNotice('Digite ENABLE para reativar o motor')
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand-mark"><span /><span /><span /></div>
      <div className="brand-word">ALG<span>O</span></div>
      <div className="nav-list">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${activePage === id ? 'active' : ''}`} onClick={() => navigate(id)}><Icon size={19} strokeWidth={1.7} /><span>{label}</span></button>)}</div>
      <div className="sidebar-bottom"><div className="side-divider" /><button className="nav-item"><Network size={18} /><span>Connect</span></button><span className="version">v0.1.0 · {modeLabel}</span></div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="breadcrumb"><span>ALGODESK</span><ChevronRight size={14} /><b>{navItems.find((item) => item.id === activePage)?.label.toUpperCase()}</b></div><div className="top-actions"><span className={`connection ${feedStatus === 'offline' ? 'is-offline' : ''}`}><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'websocket' ? 'Binance WebSocket' : feedStatus === 'rest' ? 'Binance REST connected' : 'Binance feed unavailable'}</span><span className="top-time">{currentTime} BRT</span><button className="icon-button" aria-label="Notificações"><Bell size={17} /></button><button className="avatar-user">AD</button><span className="user-name">AlgoTrader</span></div></header>

      <div className="content">
        <div className="page-heading"><div><p className="section-kicker">SALA DE OPERAÇÕES · BINANCE SPOT · DADOS PÚBLICOS</p><h1>{activePage === 'operations' ? 'Sala de Operações' : navItems.find((item) => item.id === activePage)?.label}</h1><p className="heading-sub">{activePage === 'operations' ? `${engineHeadline}. Cinco estações visuais transparentes.` : 'Observe e valide cada decisão dentro dos limites de segurança.'}</p></div><div className="heading-controls"><div className="search-box"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar robô..." aria-label="Buscar robô" /></div><div className="mode-select"><span className="mode-dot" />{modeLabel} · LIVE BLOQUEADO<ChevronRight size={14} /></div></div></div>
        <div className="stats-row"><StatCard label="Saldo Spot · BTC/USDT" value={accountSummary?.account_value_quote !== undefined ? `$ ${accountSummary.account_value_quote.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} detail={accountSummary ? `${formatAsset(accountSummary.base_total)} ${accountSummary.base_asset ?? 'BTC'} · ${formatAsset(accountSummary.quote_total, 2)} ${accountSummary.quote_asset ?? 'USDT'}` : accountStatus === 'error' ? 'Saldo indisponível' : 'Consultando Binance'} icon={WalletCards} /><StatCard label={`${modeLabel} equity · robô`} value={paperSummary ? `$ ${paperSummary.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} detail={paperSummary?.status === 'running' ? 'Estado marcado pelo worker' : runtimeIssue ? 'Trading pausado pelo risco' : 'Engine aquecendo'} icon={Bot} /><StatCard label={`${modeLabel} PnL total`} value={formatSignedUsd(paperSummary?.total_pnl ?? paperSummary?.daily_pnl)} detail={paperSummary ? `Realizado ${formatSignedUsd(paperSummary.daily_pnl)} · aberto ${formatSignedUsd(paperSummary.unrealized_pnl)}` : 'Aguardando dados'} tone="cyan" icon={CircleDollarSign} /><StatCard label={`${modeLabel} drawdown`} value={paperSummary ? `${paperSummary.drawdown_percent.toFixed(2)}%` : '—'} detail={`Risk limit · ${(riskConfig?.hard_drawdown_limit_percent ?? 5).toFixed(2)}%`} tone="red" icon={Gauge} /><button className={`stop-button ${hardStopped ? 'is-stopped' : ''}`} onClick={hardStopped ? () => setHardStopped(false) : stopAll}><Square size={17} fill="currentColor" />{hardStopped ? 'HARD STOP ACTIVE' : 'PARAR TODOS OS ROBÔS'}</button></div>

      <PageWorkspace page={activePage} bots={bots} botsOnline={botsOnline} onSelect={selectBot} backtest={backtestMetrics} backtestMeta={backtestMeta} backtestState={backtestState} backtestSplits={backtestSplits} parameterSweepCount={parameterSweepCount} walkForwardFolds={walkForwardFolds} paperSummary={paperSummary} systemMetrics={systemMetrics} riskConfig={riskConfig} equityPoints={equityPoints} paperActivities={paperActivities} />
        {activePage === 'operations' && <div className="operations-grid">
          <section className="desk-panel"><div className="desk-panel-header"><div><span className="panel-eyebrow"><Radio size={13} /> {modeLabel} {modeLabel === 'PAPER' ? 'SIMULATION' : 'SPOT'}</span><h2>Trading floor</h2></div><div className="desk-legend"><span><i className="legend-dot cyan" />Open</span><span><i className="legend-dot violet" />Scanning</span><span><i className="legend-dot amber" />Waiting</span><span><i className="legend-dot red" />Halted</span></div></div>
            <div className="trading-floor"><div className="floor-back-wall"><div className="wall-screen screen-map"><span>MARKET GRID</span><div className="world-dots" /></div><div className="wall-screen screen-chart"><span>BTC / ETH · BINANCE PUBLIC</span><div className="market-values"><b>₿ {livePrices.BTCUSDT ? `$${livePrices.BTCUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b><b>Ξ {livePrices.ETHUSDT ? `$${livePrices.ETHUSDT.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div><small className="market-source">{feedStatus === 'websocket' ? 'LIVE WEBSOCKET TICKER' : feedStatus === 'rest' ? 'LIVE REST TICKER' : 'NO LIVE MARKET FEED'}</small><Sparkline /></div><div className="wall-copy">DISCIPLINE<br /><em>BEATS</em><br />EMOTION</div></div><div className="floor-grid" /><div className="floor-light light-one" /><div className="floor-light light-two" />{visibleBots.map((bot, index) => <DeskStation bot={bot} index={index} key={bot.id} onSelect={() => selectBot(bot)} selected={selectedBot?.id === bot.id} />)}<div className="floor-label">ALGODESK <span>///</span> {modeLabel} CONTROL FLOOR</div></div>
          </section>
          <aside className="activity-panel"><div className="activity-header"><div><span className="panel-eyebrow"><Activity size={13} /> {modeLabel} SYSTEM LOG</span><h2>Activity feed</h2></div><button className="filter-button">All bots <ChevronRight size={13} /></button></div><div className="activity-list">{displayActivities.map((item, index) => <button className="activity-item" key={`${item.time}-${index}`} onClick={() => { const bot = bots.find((candidate) => candidate.id === item.bot || (candidate.id === 'BOT-001' && item.bot === 'ema-btc-01')); if (bot) selectBot(bot) }}><div className="activity-rail"><StatusMark tone={item.tone} pulse={index === 0} /><span /></div><div className="activity-copy"><div className="activity-meta"><time>{item.time}</time><strong>{item.bot}</strong><em className={toneClass(item.tone)}>{item.label}</em></div><p>{item.text}</p></div></button>)}</div><button className="view-all">View full {modeLabel.toLowerCase()} event log <ChevronRight size={14} /></button></aside>
        </div>}

        <footer className="bottom-strip"><div className="allocation"><span className="strip-label">{modeLabel} PORTFOLIO ALLOCATION</span><div className="allocation-body"><div className="donut" style={{ background: `conic-gradient(var(--cyan) 0 ${paperSummary?.allocation_percent ?? 0}%, #18364c ${paperSummary?.allocation_percent ?? 0}% 100%)` }}><span>{(paperSummary?.allocation_percent ?? 0).toFixed(0)}%</span></div><div className="allocation-keys"><span><i className="legend-dot cyan" />{paperSummary?.symbol ?? 'BTCUSDT'} <b>{(paperSummary?.allocation_percent ?? 0).toFixed(0)}%</b></span></div></div></div><div className="strip-stat"><span className="strip-label">{modeLabel} OPEN POSITIONS</span><strong>{paperSummary?.open_positions ?? 0}</strong><small>Active {engineLabel.toLowerCase()}</small></div><div className="strip-stat positive-stat"><span className="strip-label">{modeLabel} REALIZED PNL</span><strong>{formatSignedUsd(paperSummary?.realized_pnl_24h)}</strong><small>Engine · {paperSummary?.trades_24h ?? 0} closed trades</small></div><div className="strip-stat"><span className="strip-label">{modeLabel} WIN RATE</span><strong>{paperSummary ? `${paperSummary.win_rate_24h.toFixed(0)}%` : '—'}</strong><small>Realized {modeLabel.toLowerCase()} trades</small></div><div className="strip-stat"><span className="strip-label">DATA SOURCE</span><strong>BINANCE</strong><small>Closed {paperSummary?.interval ?? '1h'} candles</small></div><div className="system-status"><span className="strip-label">SYSTEM STATUS</span><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'websocket' ? 'Binance WebSocket' : feedStatus === 'rest' ? 'Binance REST connected' : 'Binance feed unavailable'}</div><div><StatusMark tone={feedStatus === 'offline' ? 'amber' : 'cyan'} pulse={feedStatus !== 'offline'} /> {feedStatus === 'offline' ? 'Market data offline' : 'Market data live'}</div><div><StatusMark tone={hardStopped ? 'red' : 'amber'} /> {hardStopped ? `${engineLabel} halted` : runtimeIssue ? `${engineLabel} paused` : paperSummary?.status === 'error' ? `${engineLabel} error` : paperSummary?.status === 'running' ? `${engineLabel} running` : `${engineLabel} starting`}</div><div><StatusMark tone={accountStatus === 'connected' ? 'cyan' : 'amber'} /> {accountStatus === 'connected' ? 'Account read-only connected' : accountStatus === 'not-configured' ? 'Account not configured' : accountStatus === 'loading' ? 'Account status loading' : 'Account read failed'}</div></div><div className="strip-pulse"><Sparkline /><span>{feedStatus === 'offline' ? 'OFFLINE' : 'STABLE'}</span></div></footer>
      </div>
    </main>

    {selectedBot && <div className="inspector"><div className="inspector-top"><span>BOT INSPECTOR</span><button onClick={() => setSelectedBot(null)} aria-label="Fechar inspetor"><X size={15} /></button></div><div className="inspector-hero"><BotAvatar status={selectedBot.status} tone={selectedBot.tone} /><div><strong>{selectedBot.id}</strong><span>{selectedBot.strategy}</span></div></div><div className="inspector-status"><StatusMark tone={selectedBot.tone} pulse={selectedBot.status === 'SCANNING'} /><b>{selectedBot.status}</b><span>• {selectedBot.position}</span></div><div className="inspector-grid"><div><small>SYMBOL</small><b>{selectedBot.symbol}</b></div><div><small>PnL</small><b className={selectedBot.pnl.startsWith('-') ? 'negative' : 'positive'}>{selectedBot.pnl}</b></div><div><small>TIMEFRAME</small><b>{paperSummary?.interval ?? '1h'}</b></div><div><small>RISK LIMIT</small><b>{riskConfig ? `${riskConfig.max_position_percent.toFixed(2)}%` : '—'}</b></div></div><div className="inspector-chart"><span>POSITION TELEMETRY</span><Sparkline /></div><p className="inspector-note">{selectedBot.activity}</p><button className="inspector-action" onClick={() => setNotice(`${selectedBot.id}: ação manual bloqueada no modo ${modeLabel}`)}><SlidersHorizontal size={15} /> View strategy config</button></div>}

    {hardStopped && <div className="stop-modal-backdrop"><div className="stop-modal"><div className="modal-icon"><ShieldAlert size={22} /></div><span className="section-kicker">SAFETY INTERLOCK</span><h2>Hard stop active</h2><p>{runtimeIssue && <><strong>Motivo: {runtimeIssue}</strong><br /></>}Novas ordens e ordens pendentes estão bloqueadas no {engineLabel.toLowerCase()}. Para reativar, digite <strong>ENABLE</strong>.</p><input value={enableText} onChange={(event) => setEnableText(event.target.value)} placeholder="Digite ENABLE" autoFocus /><div className="modal-actions"><button className="ghost-button" onClick={() => setNotice('HARD STOP permanece ativo')}>Keep stopped</button><button className="primary-button" onClick={reenable}>Re-enable engine <Zap size={15} /></button></div></div></div>}
    {notice && <div className="toast"><StatusMark tone="cyan" />{notice}</div>}
  </div>
}

export default App
