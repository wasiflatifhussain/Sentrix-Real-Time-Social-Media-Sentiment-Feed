package com.sentrix.ingestor_service.messaging.producer;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.header.internals.RecordHeader;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class KafkaEventPublisher {

  @Value("${app.kafka.topic}")
  private String kafkaTopic;

  private final KafkaTemplate<String, String> kafkaTemplate;

  /**
   * Publishes a JSON payload into the single ingestor topic.
   *
   * <p>key: stable identifier (use eventId / dedupKey) value: JSON string headers: optional
   * metadata for debugging/routing
   */
  public CompletableFuture<Void> publish(
      String key, String json, String source, String entityType) {
    ProducerRecord<String, String> record = new ProducerRecord<>(kafkaTopic, key, json);

    record
        .headers()
        .add(new RecordHeader("source", source.getBytes(StandardCharsets.UTF_8)))
        .add(new RecordHeader("entityType", entityType.getBytes(StandardCharsets.UTF_8)));

    CompletableFuture<SendResult<String, String>> future = kafkaTemplate.send(record);

    return future
        .thenAccept(
            result -> {
              // Keep per-message logs at DEBUG to avoid spam
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
                log.error(
                    "[KAFKA_PUB_FAIL] topic={} key={} err={}", kafkaTopic, key, ex.toString());
              }
            });
  }
}
