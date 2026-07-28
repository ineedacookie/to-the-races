interface PendingActionOptions<Key> {
  key: Key;
  pending: Set<Key>;
  action: () => Promise<void>;
  onPendingChange: () => void;
  onError: (error: unknown) => void | Promise<void>;
}

export async function runPendingAction<Key>({
  key,
  pending,
  action,
  onPendingChange,
  onError,
}: PendingActionOptions<Key>): Promise<void> {
  if (pending.has(key)) {
    return;
  }

  pending.add(key);
  onPendingChange();
  try {
    await action();
  } catch (error: unknown) {
    await onError(error);
  } finally {
    pending.delete(key);
    onPendingChange();
  }
}
