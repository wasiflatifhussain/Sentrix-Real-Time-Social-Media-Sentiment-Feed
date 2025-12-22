package com.sentrix.filtering_service_a.processing.validation;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.EventFeatures;
import com.sentrix.filtering_service_a.model.service_a.FilterReason;
import com.sentrix.filtering_service_a.model.service_a.TextView;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class ServiceAValidator implements Validator {

  @Value("${app.validation.min-text-len:10}")
  private int minTextLen;

  // In days; 0 means no age check
  @Value("${app.validation.max-event-age-days:0}")
  private int maxAgeDays;

  @Value("${app.validation.drop-on-truncate:false}")
  private boolean dropOnTruncate;

  @Override
  public ValidationResult validate(IngestorEvent event, TextView textView, EventFeatures features) {
    if (event == null) return ValidationResult.drop(FilterReason.MALFORMED_EVENT);
    if (textView == null || isBlank(textView.getTextNormalized())) {
      return ValidationResult.drop(FilterReason.EMPTY_TEXT);
    }

    // 1) Too short normalized text
    // Kept at 10 to account for comments
    if (minTextLen > 0 && textView.getTextNormalized().length() < minTextLen) {
      return ValidationResult.drop(FilterReason.TOO_SHORT_TEXT);
    }

    // 2) Truncation policy
    if (dropOnTruncate && textView.isWasTruncated()) {
      return ValidationResult.drop(FilterReason.OVERSIZE_TRUNCATED);
    }

    // 3) Too old
    if (maxAgeDays > 0) {
      long createdAtUtc = event.getCreatedAtUtc(); // it's epoch seconds
      if (createdAtUtc > 0) {
        long nowSec = Instant.now().getEpochSecond();
        long ageSec = nowSec - createdAtUtc;
        long maxSec = (long) maxAgeDays * 24L * 3600L;
        if (ageSec > maxSec) {
          return ValidationResult.drop(FilterReason.TOO_OLD);
        }
      }
    }

    return ValidationResult.ok();
  }

  private static boolean isBlank(String s) {
    return s == null || s.trim().isEmpty();
  }
}
