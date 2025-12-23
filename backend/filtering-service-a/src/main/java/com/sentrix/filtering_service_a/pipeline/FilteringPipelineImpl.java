package com.sentrix.filtering_service_a.pipeline;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.*;
import com.sentrix.filtering_service_a.pipeline.dedup.DedupService;
import com.sentrix.filtering_service_a.pipeline.feature_checks.EventFeatureChecks;
import com.sentrix.filtering_service_a.pipeline.features.FeatureExtractor;
import com.sentrix.filtering_service_a.pipeline.normalizer.Normalizer;
import com.sentrix.filtering_service_a.pipeline.validation.ValidationResult;
import com.sentrix.filtering_service_a.pipeline.validation.Validator;
import java.time.Instant;
import java.util.Optional;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@AllArgsConstructor
public class FilteringPipelineImpl implements FilteringPipeline {

  private final Normalizer normalizer;
  private final FeatureExtractor featureExtractor;
  private final Validator validator;
  private final DedupService dedupService;
  private final EventFeatureChecks eventFeatureChecks;

  @Override
  public FilteredEventEnvelope process(IngestorEvent event) {

    // Phase 1: Basic validation and rejections
    if (event == null) {
      return dropEvent(null, FilterReason.MALFORMED_EVENT);
    }
    if (isBlank(event.getEventId()) && isBlank(event.getDedupKey())) {
      return dropEvent(event, FilterReason.MISSING_REQUIRED_FIELD);
    }
    if (event.getSource() == null) {
      return dropEvent(event, FilterReason.INVALID_SOURCE);
    }
    if (event.getEntityType() == null) {
      return dropEvent(event, FilterReason.INVALID_EVENT_TYPE);
    }

    String combinedText = combineText(event.getTitle(), event.getText());
    if (isBlank(combinedText)) {
      return dropEvent(event, FilterReason.EMPTY_TEXT);
    }

    // Phase 2: Normalization + Event Features Extraction
    TextView textView = normalizer.normalize(event, combinedText);
    if (textView == null || isBlank(textView.getTextNormalized())) {
      return dropEvent(event, FilterReason.EMPTY_TEXT);
    }
    EventFeatures features = featureExtractor.extract(event, textView);

    log.debug(
        "[A_PIPELINE] KEEP eventId={} words={} urls={} capsRatio={} emojis={}",
        event.getEventId(),
        features.getWordCount(),
        features.getUrlCount(),
        features.getCapsRatio(),
        features.getEmojiCount());

    // Phase 3: Hard validations
    ValidationResult validationResult = validator.validate(event, textView, features);
    if (!validationResult.isOk()) {
      return dropEvent(event, validationResult.getReason(), textView, features);
    }

    // Phase 4: Deduplication using dedup-key and content hash
    long eventEpochSeconds =
        (event.getCreatedAtUtc() != null && event.getCreatedAtUtc() > 0)
            ? event.getCreatedAtUtc()
            : event.getIngestedAtUtc();

    Optional<FilterReason> dedupReasonOpt =
        dedupService.checkAndMark(
            event.getSource().name().toLowerCase(), // eg: "reddit"
            event.getDedupKey(),
            textView.getTextNormalized(),
            event.getTicker(),
            eventEpochSeconds);

    if (dedupReasonOpt.isPresent()) {
      return dropEvent(event, dedupReasonOpt.get(), textView, features);
    }

    // Phase 5: Event Feature based heuristic checks
    Optional<FilterReason> featureCheckDropOpt = eventFeatureChecks.shouldDrop(features);
    if (featureCheckDropOpt.isPresent()) {
      return dropEvent(event, featureCheckDropOpt.get(), textView, features);
    }

    return FilteredEventEnvelope.builder()
        .ingestorEvent(event)
        .filterMeta(
            FilterMeta.builder()
                .filterStage("service_a")
                .decision(Decision.KEEP)
                .filterReason(null)
                .processedAtUtc(Instant.now().getEpochSecond())
                .build())
        .textView(textView)
        .eventFeatures(features)
        .build();
  }

  private static FilteredEventEnvelope dropEvent(IngestorEvent event, FilterReason reason) {
    return dropEvent(event, reason, null, null);
  }

  private static FilteredEventEnvelope dropEvent(
      IngestorEvent event, FilterReason reason, TextView textView, EventFeatures features) {
    return FilteredEventEnvelope.builder()
        .ingestorEvent(event)
        .filterMeta(
            FilterMeta.builder()
                .filterStage("service_a")
                .decision(Decision.DROP)
                .filterReason(reason)
                .processedAtUtc(Instant.now().getEpochSecond())
                .build())
        .textView(textView)
        .eventFeatures(features)
        .build();
  }

  private static String combineText(String title, String text) {
    if (isBlank(title)) return text;
    if (isBlank(text)) return title;
    return title + "\n" + text;
  }

  private static boolean isBlank(String s) {
    return s == null || s.trim().isEmpty();
  }
}
