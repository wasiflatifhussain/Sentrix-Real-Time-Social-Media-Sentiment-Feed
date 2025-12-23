package com.sentrix.filtering_service_a.messaging.producer;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.header.internals.RecordHeader;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class KafkaEnvelopePublisher {

  private final KafkaTemplate<String, String> kafkaTemplate;

  public CompletableFuture<Void> publish(
      String topic,
      String key,
      String json,
      String source,
      String entityType,
      String decision,
      String filterReason // null allowed (for KEEP)
      ) {

    ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, json);

    if (source != null) {
      record.headers().add(new RecordHeader("source", bytes(source)));
    }
    if (entityType != null) {
      record.headers().add(new RecordHeader("entityType", bytes(entityType)));
    }
    if (decision != null) {
      record.headers().add(new RecordHeader("decision", bytes(decision)));
    }
    if (filterReason != null) {
      record.headers().add(new RecordHeader("filterReason", bytes(filterReason)));
    }

    CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send(record);

    return future
        .thenAccept(
            result -> {
              if (log.isDebugEnabled()) {
                var m = result.getRecordMetadata();
                log.debug(
                    "[KAFKA_PUB] topic={} partition={} offset={} key={}",
                    m.topic(),
                    m.partition(),
                    m.offset(),
                    key);
              }
            })
        .whenComplete(
            (ok, ex) -> {
              if (ex != null) {
                log.error("[KAFKA_PUB_FAIL] topic={} key={} err={}", topic, key, ex.toString());
              }
            });
  }

  private static byte[] bytes(String s) {
    return s.getBytes(StandardCharsets.UTF_8);
  }
}
