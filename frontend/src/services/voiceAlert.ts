export interface SafeVoiceAlertInput {
  title: string;
  message: string;
  level: string;
}

export function shouldVoiceAlert(alert: SafeVoiceAlertInput, enabled: boolean, muted: boolean): boolean {
  return enabled && !muted && ['critical', 'alert'].includes(String(alert.level).toLowerCase());
}

/** Keep spoken content to the persisted safe notification fields only. */
export function buildSafeVoiceMessage(alert: SafeVoiceAlertInput): string {
  return `${alert.title}. ${alert.message}`.replace(/[\r\n]+/g, ' ').slice(0, 240);
}
