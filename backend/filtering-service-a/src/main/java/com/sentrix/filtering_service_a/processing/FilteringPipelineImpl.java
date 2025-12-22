package com.sentrix.filtering_service_a.processing;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class FilteringPipelineImpl implements FilteringPipeline {

  @Override
  public FilteredEventEnvelope process(IngestorEvent event) {

    // use hard-exits for failures
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

    // TODO: normalize + event features extraction here
    log.debug(
        "[A_PIPELINE] features/normalization not implemented yet; passing KEEP eventId={}",
        event.getEventId());

    TextView textView =
        TextView.builder()
            .textNormalized(null) // TODO: insert result from normalization impl
            .wasTruncated(false) // TODO: determine during normalization
            .originalTextLength(combinedText.length())
            .build();

    return FilteredEventEnvelope.builder()
        .ingestorEvent(event)
        .filterMeta(
            FilterMeta.builder()
                .filterStage("service_a")
                .decision(Decision.KEEP)
                .filterReason(null)
                .processedAtUtc(System.currentTimeMillis())
                .build())
        .textView(textView)
        .eventFeatures(null) // TODO: insert result from event feature impl
        .build();
  }

  private static FilteredEventEnvelope dropEvent(IngestorEvent event, FilterReason reason) {
    return FilteredEventEnvelope.builder()
        .ingestorEvent(event)
        .filterMeta(
            FilterMeta.builder()
                .filterStage("service_a")
                .decision(Decision.DROP)
                .filterReason(reason)
                .processedAtUtc(System.currentTimeMillis())
                .build())
        .textView(null)
        .eventFeatures(null)
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
