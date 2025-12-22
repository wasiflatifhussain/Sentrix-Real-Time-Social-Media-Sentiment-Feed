package com.sentrix.filtering_service_a.service;

import com.sentrix.filtering_service_a.messaging.producer.KafkaEnvelopePublisher;
import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.Decision;
import com.sentrix.filtering_service_a.model.service_a.FilterMeta;
import com.sentrix.filtering_service_a.model.service_a.FilterReason;
import com.sentrix.filtering_service_a.model.service_a.FilteredEventEnvelope;
import com.sentrix.filtering_service_a.processing.FilteringPipeline;
import com.sentrix.filtering_service_a.util.EventKeyUtil;
import com.sentrix.filtering_service_a.util.KafkaHeaderUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class IngestorEventHandler {

  @Value("${app.kafka.topic.cleaned}")
  private String cleanedTopic;

  @Value("${app.kafka.topic.dropped}")
  private String droppedTopic;

  private final ObjectMapper objectMapper;
  private final FilteringPipeline filteringPipeline;
  private final KafkaEnvelopePublisher kafkaEnvelopePublisher;

  public void handleIngestorEvent(ConsumerRecord<String, String> rec, Acknowledgment ack) {
    final String sourceHeader = KafkaHeaderUtil.header(rec, "source");
    final String entityTypeHeader = KafkaHeaderUtil.header(rec, "entityType");

    final IngestorEvent ingestorEvent;
    try {
      ingestorEvent = objectMapper.readValue(rec.value(), IngestorEvent.class);
    } catch (Exception ex) {
      // Poison message policy: publish to dropped with MALFORMED_EVENT, then ack.
      log.error(
          "[A_RAW_PARSE_FAIL] topic={} partition={} offset={} key={} err={}",
          rec.topic(),
          rec.partition(),
          rec.offset(),
          rec.key(),
          ex.toString());

      FilteredEventEnvelope droppedEnvelope =
          FilteredEventEnvelope.builder()
              .ingestorEvent(null)
              .filterMeta(
                  FilterMeta.builder()
                      .filterStage("service_a")
                      .decision(Decision.DROP)
                      .filterReason(FilterReason.RAW_PARSE_FAIL)
                      .processedAtUtc(System.currentTimeMillis())
                      .build())
              .textView(null)
              .eventFeatures(null)
              .build();

      tryPublishAndAck(
          droppedTopic,
          rec.key(),
          droppedEnvelope,
          sourceHeader,
          entityTypeHeader,
          Decision.DROP,
          FilterReason.RAW_PARSE_FAIL,
          ack);

      return;
    }

    // Process through filtering pipeline
    FilteredEventEnvelope filteredEventEnvelope;
    try {
      filteredEventEnvelope = filteringPipeline.process(ingestorEvent);
    } catch (Exception ex) {
      // Choose policy: drop + audit (recommended) OR retry (by not acking)
      log.error(
          "[PIPELINE_CALL_FAIL] key={} eventId={} err={}",
          rec.key(),
          ingestorEvent.getEventId(),
          ex.toString());

      FilteredEventEnvelope droppedEnvelope =
          FilteredEventEnvelope.builder()
              .ingestorEvent(ingestorEvent)
              .filterMeta(
                  FilterMeta.builder()
                      .filterStage("service_a")
                      .decision(Decision.DROP)
                      .filterReason(FilterReason.PIPELINE_CALL_FAIL)
                      .processedAtUtc(System.currentTimeMillis())
                      .build())
              .textView(null)
              .eventFeatures(null)
              .build();

      tryPublishAndAck(
          droppedTopic,
          EventKeyUtil.stableKey(ingestorEvent, rec.key()),
          droppedEnvelope,
          ingestorEvent.getSource() == null ? sourceHeader : ingestorEvent.getSource().name(),
          ingestorEvent.getEntityType() == null
              ? entityTypeHeader
              : ingestorEvent.getEntityType().name(),
          Decision.DROP,
          FilterReason.PIPELINE_CALL_FAIL,
          ack);

      return;
    }

    // Publish based on decision
    Decision decision = filteredEventEnvelope.getFilterMeta().getDecision();
    FilterReason reason = filteredEventEnvelope.getFilterMeta().getFilterReason();

    String outTopic = (decision == Decision.KEEP) ? cleanedTopic : droppedTopic;
    String outKey = EventKeyUtil.stableKey(ingestorEvent, rec.key());

    String src =
        (ingestorEvent.getSource() != null) ? ingestorEvent.getSource().name() : sourceHeader;
    String et =
        (ingestorEvent.getEntityType() != null)
            ? ingestorEvent.getEntityType().name()
            : entityTypeHeader;

    tryPublishAndAck(outTopic, outKey, filteredEventEnvelope, src, et, decision, reason, ack);
  }

  private void tryPublishAndAck(
      String topic,
      String key,
      FilteredEventEnvelope envelope,
      String source,
      String entityType,
      Decision decision,
      FilterReason reason,
      Acknowledgment ack) {

    final String json;
    try {
      json = objectMapper.writeValueAsString(envelope);
    } catch (Exception ex) {
      log.error("[A_ENVELOPE_SERIALIZE_FAIL] topic={} key={} err={}", topic, key, ex.toString());
      return;
    }

    kafkaEnvelopePublisher
        .publish(
            topic,
            key,
            json,
            source,
            entityType,
            decision.name(),
            reason == null ? null : reason.name())
        .thenRun(ack::acknowledge);
  }
}
