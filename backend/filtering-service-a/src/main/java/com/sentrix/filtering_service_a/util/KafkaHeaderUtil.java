package com.sentrix.filtering_service_a.util;

import java.nio.charset.StandardCharsets;
import org.apache.kafka.clients.consumer.ConsumerRecord;

public final class KafkaHeaderUtil {
  private KafkaHeaderUtil() {}

  public static String header(ConsumerRecord<String, String> rec, String key) {
    var h = rec.headers().lastHeader(key);
    return (h == null) ? null : new String(h.value(), StandardCharsets.UTF_8);
  }
}
