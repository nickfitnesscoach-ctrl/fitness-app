export const PAYMENT_STATUS_BADGES: Record<string, string> = {
  succeeded: 'bg-green-100 text-green-800',
  pending: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  canceled: 'bg-gray-100 text-gray-800',
  refunded: 'bg-blue-100 text-blue-800',
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  succeeded: 'Успешно',
  pending: 'В ожидании',
  failed: 'Ошибка',
  canceled: 'Отменён',
  refunded: 'Возврат',
};
