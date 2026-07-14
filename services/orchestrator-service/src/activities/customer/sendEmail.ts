import { notificationService } from "../../services/notificationService";
import { INotificationPayload } from "../../types/notification";

export async function sendEmail(payload: INotificationPayload) {
  return notificationService.event(payload);
}
