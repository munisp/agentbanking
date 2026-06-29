import { NotificationCategory, NotificationType } from "../utils/enums";

export interface INotificationPayload {
  payload: any;
  subscriberId: string;
  createSubscriber?: boolean;
  subscriber?: ISubscriberPayload;
  type: NotificationType;
  category: NotificationCategory;
}

export interface ISubscriberTraits {
  email: string;
  phone?: string;
  firstName?: string;
  lastName?: string;
  deviceToken?: string;
  wallet?: string;
}

export interface ISubscriberPayload {
  subscriberId: string;
  traits: ISubscriberTraits;
}
