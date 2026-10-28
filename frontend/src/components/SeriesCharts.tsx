/**
 * Temperature and humidity charts (ApexCharts). Loaded lazily: ApexCharts is the
 * heaviest dependency and only the fridge page needs it.
 */
import Chart from 'react-apexcharts'
import type { ApexOptions } from 'apexcharts'
import type { Fridge, Series } from '../lib/types'

const INK = '#0f1d2b'
const MUTED = '#5b6b78'
const LINE = '#d5dde1'
const OK = '#17855a'
const ICE = '#0b7f95'
const ALERT = '#d9412b'
const MONO = "'JetBrains Mono', ui-monospace, monospace"

function baseOptions(unit: string, decimals: number): ApexOptions {
  return {
    chart: {
      type: 'line',
      height: 280,
      fontFamily: "'Instrument Sans Variable', sans-serif",
      foreColor: MUTED,
      toolbar: { show: true, tools: { download: true, zoom: true, zoomin: true, zoomout: true, pan: false, reset: true, selection: false } },
      zoom: { enabled: true, type: 'x' },
      animations: { enabled: false },
      defaultLocale: 'fr',
      locales: [
        {
          name: 'fr',
          options: {
            months: ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
            shortMonths: ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'],
            days: ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'],
            shortDays: ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.'],
            toolbar: { download: 'Télécharger', zoomIn: 'Zoom avant', zoomOut: 'Zoom arrière', reset: 'Réinitialiser' },
          },
        },
      ],
    },
    stroke: { width: 2, curve: 'straight' },
    markers: { size: 0, hover: { size: 4 } },
    grid: { borderColor: LINE, strokeDashArray: 3 },
    xaxis: {
      type: 'datetime',
      labels: { datetimeUTC: false, style: { fontFamily: MONO, fontSize: '11px' } },
      axisBorder: { color: LINE },
      axisTicks: { color: LINE },
    },
    yaxis: {
      decimalsInFloat: decimals,
      labels: {
        style: { fontFamily: MONO, fontSize: '11px' },
        formatter: (v: number) => `${v.toFixed(decimals).replace('.', ',')} ${unit}`,
      },
    },
    tooltip: {
      x: { format: 'dd MMM yyyy · HH:mm' },
      y: { formatter: (v: number) => (v == null ? '—' : `${v.toFixed(1).replace('.', ',')} ${unit}`) },
    },
    legend: { show: false },
    noData: { text: 'Aucune mesure sur cette période' },
  }
}

function band(min: number, max: number, unit: string): NonNullable<ApexOptions['annotations']> {
  const label = (text: string) => ({
    text,
    borderWidth: 0,
    style: { background: 'transparent', color: OK, fontFamily: MONO, fontSize: '11px' },
  })
  return {
    yaxis: [
      { y: min, y2: max, fillColor: OK, opacity: 0.09, borderColor: 'transparent' },
      { y: min, borderColor: OK, strokeDashArray: 4, label: label(`min ${min} ${unit}`) },
      { y: max, borderColor: OK, strokeDashArray: 4, label: label(`max ${max} ${unit}`) },
    ],
  }
}

function yRange(values: number[], min: number, max: number) {
  let lo = min
  let hi = max
  for (const v of values) {
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  const pad = Math.max(1, (hi - lo) * 0.15)
  return { min: Math.floor(lo - pad), max: Math.ceil(hi + pad) }
}

export default function SeriesCharts({ fridge, series }: { fridge: Fridge; series: Series }) {
  const temps: [number, number | null][] = []
  const hums: [number, number | null][] = []
  const tempValues: number[] = []
  const humValues: number[] = []
  for (const m of series.results) {
    const t = new Date(m.received_at).getTime()
    temps.push([t, m.temperature])
    hums.push([t, m.humidity])
    if (m.temperature != null) tempValues.push(m.temperature)
    if (m.humidity != null) humValues.push(m.humidity)
  }

  const tempBase = baseOptions('°C', 1)
  const tempOptions: ApexOptions = {
    ...tempBase,
    colors: [INK],
    annotations: band(fridge.temp_min, fridge.temp_max, '°C'),
    yaxis: { ...tempBase.yaxis, ...yRange(tempValues, fridge.temp_min, fridge.temp_max) },
    // Points outside the band are marked in red.
    markers: {
      size: 0,
      hover: { size: 4 },
      discrete: series.results.flatMap((m, index) =>
        m.temperature != null && (m.temperature < fridge.temp_min || m.temperature > fridge.temp_max)
          ? [{ seriesIndex: 0, dataPointIndex: index, fillColor: ALERT, strokeColor: '#fff', size: 3.5 }]
          : [],
      ),
    },
  }

  const hasHumBand = fridge.hum_min != null && fridge.hum_max != null
  const humBase = baseOptions('%', 0)
  const humOptions: ApexOptions = {
    ...humBase,
    colors: [ICE],
    annotations: hasHumBand ? band(fridge.hum_min!, fridge.hum_max!, '%') : undefined,
    yaxis: {
      ...humBase.yaxis,
      ...(hasHumBand
        ? yRange(humValues, fridge.hum_min!, fridge.hum_max!)
        : { min: 0, max: 100 }),
    },
  }

  return (
    <>
      <div className="card chart-card">
        <h3>Température</h3>
        <Chart type="line" height={280} options={tempOptions} series={[{ name: 'Température', data: temps }]} />
      </div>
      <div className="card chart-card">
        <h3>Humidité</h3>
        <Chart type="line" height={240} options={humOptions} series={[{ name: 'Humidité', data: hums }]} />
      </div>
    </>
  )
}
