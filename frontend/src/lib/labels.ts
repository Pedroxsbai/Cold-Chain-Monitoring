import type {
  Channel,
  DeviceStatus,
  FridgeStatus,
  IncidentStatus,
  IncidentType,
  Role,
} from './types'

export const FRIDGE_STATUS: Record<FridgeStatus, string> = {
  normal: 'Normal',
  alert: 'Alerte',
  offline: 'Hors ligne',
}

export const INCIDENT_TYPE: Record<IncidentType, string> = {
  temperature: 'Température',
  humidity: 'Humidité',
  offline: 'Nœud hors ligne',
  sensor: 'Capteur défaillant',
}

export const INCIDENT_STATUS: Record<IncidentStatus, string> = {
  open: 'Ouvert',
  acknowledged: 'Pris en charge',
  ended: 'Terminé',
  closed: 'Clôturé',
}

export const DEVICE_STATUS: Record<DeviceStatus, string> = {
  unknown: 'Jamais vu',
  online: 'En ligne',
  offline: 'Hors ligne',
}

export const ROLE: Record<Role, string> = {
  responsible: 'Responsable frigo',
  supervisor: 'Supérieur',
  admin: 'Administrateur',
}

export const CHANNEL: Record<Channel, string> = {
  ntfy: 'Push (ntfy)',
  email: 'E-mail',
  sms: 'SMS',
  call: 'Appel',
}

export const LEVEL: Record<number, string> = {
  1: 'N1 · Responsable',
  2: 'N2 · Supérieur',
  3: 'N3 · Administrateur',
}

/** Event types of the audit trail (mirrors audit.models.EventLog.Type). */
export const EVENT_TYPES: [string, string][] = [
  ['measurement_out_of_range', 'Mesure hors plage'],
  ['sensor_failure', 'Lecture capteur invalide'],
  ['device_offline', 'Nœud hors ligne'],
  ['device_online', 'Nœud de nouveau en ligne'],
  ['device_key_rejected', 'Clé de nœud refusée'],
  ['incident_opened', 'Incident ouvert'],
  ['incident_escalated', 'Incident escaladé'],
  ['incident_acked', 'Incident pris en charge'],
  ['incident_commented', 'Commentaire ajouté'],
  ['incident_ended', 'Incident terminé'],
  ['incident_closed', 'Incident clôturé'],
  ['reagents_compromised', 'Réactifs compromis'],
  ['notification_sent', 'Notification envoyée'],
  ['notification_failed', 'Échec de notification'],
  ['notification_read', 'Notification lue'],
  ['threshold_changed', 'Seuil modifié'],
  ['object_created', 'Création'],
  ['object_updated', 'Modification'],
  ['object_deleted', 'Suppression'],
  ['user_login', 'Connexion'],
  ['user_login_failed', 'Échec de connexion'],
  ['password_reset', 'Mot de passe'],
]
