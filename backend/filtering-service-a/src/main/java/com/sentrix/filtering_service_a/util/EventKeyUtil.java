package com.sentrix.filtering_service_a.util;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;

public class EventKeyUtil {
  private EventKeyUtil() {}

  public static String stableKey(IngestorEvent e, String fallbackKey) {
    if (e == null) return fallbackKey;
    if (e.getDedupKey() != null && !e.getDedupKey().isBlank()) return e.getDedupKey();
    if (e.getEventId() != null && !e.getEventId().isBlank()) return e.getEventId();
    return fallbackKey;
  }
}
