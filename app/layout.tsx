import type { Metadata } from 'next'
import '../src/styles.css'
import './globals.css'

export const metadata: Metadata = {
  title: 'AlgoDesk · Sala de Operações',
  description: 'Pesquisa e controle de trading algorítmico na Binance Spot.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>
}
