package com.sentrix.filtering_service_a.pipeline.feature_checks;

import com.sentrix.filtering_service_a.config.EventFeatureChecksPropertiesConfig;
import com.sentrix.filtering_service_a.model.service_a.EventFeatures;
import com.sentrix.filtering_service_a.model.service_a.FilterReason;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class EventFeatureChecks {
  private final EventFeatureChecksPropertiesConfig props;

  public Optional<FilterReason> shouldDrop(EventFeatures features) {
    if (features == null) return Optional.empty();
    if (!props.isEnabled()) return Optional.empty();

    Optional<FilterReason> urlRes = checkUrlSpam(features, props.getUrlSpam());
    if (urlRes.isPresent()) return urlRes;

    Optional<FilterReason> emojiRes = checkEmoji(features, props.getEmoji());
    if (emojiRes.isPresent()) return emojiRes;

    Optional<FilterReason> repeatRes = checkRepeatChar(features, props.getRepeatChar());
    if (repeatRes.isPresent()) return repeatRes;

    Optional<FilterReason> cashRes = checkCashtags(features, props.getCashtag());
    if (cashRes.isPresent()) return cashRes;

    return Optional.empty();
  }

  // Type for c is EventFeatureChecksPropertiesConfig.UrlSpam (check
  // EventFeatureChecksPropertiesConfig.java)
  private Optional<FilterReason> checkUrlSpam(
      EventFeatures f, EventFeatureChecksPropertiesConfig.UrlSpam c) {

    int urlCount = f.getUrlCount();
    int wordCount = f.getWordCount();

    // Drop if url count exceeds hard limit
    if (urlCount >= c.getHardDropCount()) {
      return Optional.of(FilterReason.URL_SPAM_EXCESSIVE);
    }

    // Drop if url count exceeds short text limit and text is short
    if (urlCount >= c.getShortTextDropCount() && wordCount <= c.getShortTextMaxWords()) {
      return Optional.of(FilterReason.URL_SPAM_EXCESSIVE);
    }

    return Optional.empty();
  }

  private Optional<FilterReason> checkEmoji(
      EventFeatures f, EventFeatureChecksPropertiesConfig.Emoji c) {

    int emojiCount = f.getEmojiCount();
    int wordCount = f.getWordCount();

    // Drop if emoji count exceeds hard limit
    if (emojiCount >= c.getHardDropCount()) {
      return Optional.of(FilterReason.EXCESSIVE_EMOJI_SIGNAL);
    }

    // Drop if emoji count exceeds short text limit and text is short
    if (emojiCount >= c.getShortTextDropCount() && wordCount <= c.getShortTextMaxWords()) {
      return Optional.of(FilterReason.EXCESSIVE_EMOJI_SIGNAL);
    }

    return Optional.empty();
  }

  private Optional<FilterReason> checkRepeatChar(
      EventFeatures f, EventFeatureChecksPropertiesConfig.RepeatChar c) {

    int maxRunLen = f.getMaxRepeatedCharCount();
    if (maxRunLen >= c.getHardRunLen()) {
      return Optional.of(FilterReason.REPEATED_CHAR_SIGNAL);
    }

    return Optional.empty();
  }

  private Optional<FilterReason> checkCashtags(
      EventFeatures f, EventFeatureChecksPropertiesConfig.Cashtag c) {

    int cashTagCount = f.getCashTagCount();
    int wordCount = f.getWordCount();

    // Drop if cashtag count exceeds hard limit
    if (cashTagCount >= c.getHardDropCount()) {
      return Optional.of(FilterReason.MULTI_TICKER_SPAM_SIGNAL);
    }

    // Drop if cashtag count exceeds short text limit and text is short
    if (cashTagCount >= c.getShortTextDropCount() && wordCount <= c.getShortTextMaxWords()) {
      return Optional.of(FilterReason.MULTI_TICKER_SPAM_SIGNAL);
    }

    return Optional.empty();
  }
}
