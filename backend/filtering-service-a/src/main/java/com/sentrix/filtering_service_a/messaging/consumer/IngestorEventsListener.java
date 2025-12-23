package com.sentrix.filtering_service_a.messaging.consumer;

import com.sentrix.filtering_service_a.service.IngestorEventHandler;
import java.util.concurrent.atomic.AtomicLong;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class IngestorEventsListener {

  // use heartbeat logging to monitor liveness
  private static final long LOG_EVERY = 100; // possible-tune: 100/500/1000
  private final AtomicLong seen = new AtomicLong(0);
  private final IngestorEventHandler ingestorEventHandler;

  @KafkaListener(
      topics = "${app.kafka.topic.raw}",
      groupId = "${app.kafka.consumer.group-id}",
      containerFactory = "kafkaListenerContainerFactory")
  public void onIngestorEvent(ConsumerRecord<String, String> rec, Acknowledgment ack) {
    long n = seen.incrementAndGet();
    if (n % LOG_EVERY == 0) {
      log.info(
          "[A_HEARTBEAT] seen={} topic={} p={} offset={} key={}",
          n,
          rec.topic(),
          rec.partition(),
          rec.offset(),
          rec.key());
    }
    ingestorEventHandler.handleIngestorEvent(rec, ack);
  }
}
