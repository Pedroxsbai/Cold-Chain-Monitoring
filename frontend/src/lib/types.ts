export type Role = 'responsible' | 'supervisor' | 'admin'
export type FridgeStatus = 'normal' | 'alert' | 'offline'
export type IncidentType = 'temperature' | 'humidity' | 'offline' | 'sensor'
export type IncidentStatus = 'open' | 'acknowledged' | 'ended' | 'closed'
export type DeviceStatus = 'unknown' | 'online' | 'offline'
export type Channel = 'ntfy' | 'email' | 'sms' | 'call'

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Profile {
  id: number
  email: string
  first_name: string
  last_name: string
  phone: string
  ntfy_topic: string
  role: Role
  is_admin: boolean
}

export interface User extends Omit<Profile, 'is_admin'> {
  is_active: boolean
  last_login: string | null
  date_joined: string
}

export interface IncidentSummary {
  id: number
  type: IncidentType
  status: IncidentStatus
  started_at: string
  current_level: number
  excursion_minutes: number
  remaining_minutes: number
  out_of_range_now: boolean
  reagents_compromised: boolean
}

export interface Thresholds {
  temp_min: number
  temp_max: number
  hum_min: number | null
  hum_max: number | null
  max_excursion_hours: number
}

export interface Fridge extends Thresholds {
  id: number
  name: string
  location: string
  is_active: boolean
  created_at: string
  device: {
    id: number
    device_id: string
    status: DeviceStatus
    last_seen: string | null
    firmware: string
  } | null
  last_measurement: {
    temperature: number | null
    humidity: number | null
    sensor_ok: boolean
    received_at: string
  } | null
  open_incident: IncidentSummary | null
  status: FridgeStatus
}

export interface Measurement {
  id: number
  fridge: number
  fridge_name: string
  device_id: string | null
  temperature: number | null
  humidity: number | null
  sensor_ok: boolean
  received_at: string
}

export interface Series {
  fridge: number
  from: string
  to: string
  count: number
  results: Pick<Measurement, 'id' | 'temperature' | 'humidity' | 'sensor_ok' | 'received_at'>[]
}

export interface Incident extends IncidentSummary {
  fridge: number
  fridge_name: string
  type_label: string
  status_label: string
  ended_at: string | null
  notification_count: number
  last_notified_at: string | null
  severity_hours_reached: number
  acked_by: number | null
  acked_by_name: string | null
  acked_at: string | null
  closed_by: number | null
  closed_by_name: string | null
  closed_at: string | null
  closing_comment: string
  can_ack: boolean
  can_close: boolean
}

export interface IncidentComment {
  id: number
  author: number | null
  author_name: string | null
  text: string
  created_at: string
}

export interface NotificationRow {
  id: number
  user: number | null
  user_name: string | null
  channel: Channel
  kind: 'alert' | 'resolved'
  level: number
  status: 'pending' | 'sent' | 'failed'
  error: string
  sent_at: string | null
  read_at: string | null
}

export interface IncidentDetail extends Incident {
  comments: IncidentComment[]
  notifications: NotificationRow[]
}

export interface Device {
  id: number
  device_id: string
  fridge: number | null
  fridge_name: string | null
  status: DeviceStatus
  last_seen: string | null
  firmware: string
  created_at: string
}

export interface EscalationEntry {
  id: number
  fridge: number
  level: 1 | 2 | 3
  user: number
  user_email: string
  user_name: string
}

export interface EventLog {
  id: number
  timestamp: string
  type: string
  type_label: string
  actor: number | null
  actor_label: string
  object_type: string
  object_id: string
  object_repr: string
  details: Record<string, unknown>
}

export interface AckInfo {
  incident: {
    id: number
    fridge_name: string
    type: IncidentType
    type_label: string
    status: IncidentStatus
    status_label: string
    started_at: string
    ended_at: string | null
    current_level: number
    excursion_minutes: number
    remaining_minutes: number
    max_excursion_hours: number
    reagents_compromised: boolean
  }
  recipient: string
  link_used: boolean
  can_ack: boolean
}
