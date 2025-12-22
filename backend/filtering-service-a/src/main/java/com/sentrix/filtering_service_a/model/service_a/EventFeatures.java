package com.sentrix.filtering_service_a.model.service_a;

import java.util.List;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class EventFeatures {
  private int wordCount;
  private int charCount;

  private int urlCount; // not store URLs to avoid cyber threats

  private int hashtagCount;
  private List<String> extractedHashtags;

  private int mentionCount;
  private List<String> extractedMentions;

  private int cashTagCount;
  private List<String> extractedCashTags;

  private double capsRatio;
  private int emojiCount;

  private int maxRepeatedCharCount;
}
