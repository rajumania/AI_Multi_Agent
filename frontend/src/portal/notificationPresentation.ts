import { NotificationItem } from '../types';

export function unreadNotificationCount(items: NotificationItem[]): number {
  return items.reduce((count, item) => count + (item.read ? 0 : 1), 0);
}

export function recentNotifications(items: NotificationItem[], limit = 8): NotificationItem[] {
  return [...items].sort((left, right) => right.created_at.localeCompare(left.created_at)).slice(0, limit);
}
