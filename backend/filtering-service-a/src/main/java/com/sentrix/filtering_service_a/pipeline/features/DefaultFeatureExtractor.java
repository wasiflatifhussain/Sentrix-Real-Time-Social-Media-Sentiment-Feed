package com.sentrix.filtering_service_a.pipeline.features;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.EventFeatures;
import com.sentrix.filtering_service_a.model.service_a.TextView;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class DefaultFeatureExtractor implements FeatureExtractor {

  // As URL has been normalized to "<URL>"
  private static final Pattern URL_TOKEN = Pattern.compile("(?i)<URL>");

  private static final Pattern HASHTAG = Pattern.compile("(?<!\\w)#([A-Za-z0-9_]{1,50})");
  private static final Pattern MENTION = Pattern.compile("(?<!\\w)@([A-Za-z0-9_]{1,30})");
  private static final Pattern CASHTAG = Pattern.compile("\\$([A-Za-z]{1,10})");

  @Override
  public EventFeatures extract(IngestorEvent ingestorEvent, TextView textView) {
    String text = (textView == null) ? null : textView.getTextNormalized();
    if (text == null || text.trim().isEmpty()) {
      return EventFeatures.builder()
          .wordCount(0)
          .charCount(0)
          .urlCount(0)
          .hashtagCount(0)
          .extractedHashtags(List.of())
          .mentionCount(0)
          .extractedMentions(List.of())
          .cashTagCount(0)
          .extractedCashTags(List.of())
          .capsRatio(0.0)
          .emojiCount(0)
          .maxRepeatedCharCount(0)
          .build();
    }

    int charCount = text.length();
    int wordCount = countWords(text);
    int urlCount = countMatches(URL_TOKEN, text);

    List<String> hashtags = extractUnique(HASHTAG, text, 1, true, "#");
    List<String> mentions = extractUnique(MENTION, text, 1, true, "@");
    // Cashtags already normalized to uppercase in normalizer
    List<String> cashtags = extractUnique(CASHTAG, text, 1, false, "$");

    double capsRatio = computeCapsRatio(text);
    int emojiCount = countEmojiCodepoints(text);
    int maxRepeatedCharCount = maxRepeatedCharRun(text);

    return EventFeatures.builder()
        .wordCount(wordCount)
        .charCount(charCount)
        .urlCount(urlCount)
        .hashtagCount(hashtags.size())
        .extractedHashtags(hashtags)
        .mentionCount(mentions.size())
        .extractedMentions(mentions)
        .cashTagCount(cashtags.size())
        .extractedCashTags(cashtags)
        .capsRatio(capsRatio)
        .emojiCount(emojiCount)
        .maxRepeatedCharCount(maxRepeatedCharCount)
        .build();
  }

  // Count words in a string by splitting on whitespace
  // Not counting chars
  private static int countWords(String s) {
    String t = s.trim();
    if (t.isEmpty()) return 0;
    return t.split("\\s+").length;
  }

  private static int countMatches(Pattern p, String s) {
    Matcher m = p.matcher(s);
    int n = 0;
    while (m.find()) n++;
    return n;
  }

  private static List<String> extractUnique(
      Pattern p, String text, int group, boolean lower, String prefix) {
    Set<String> out = new LinkedHashSet<>();
    Matcher m = p.matcher(text);
    while (m.find()) {
      String v = m.group(group);
      if (v == null || v.isBlank()) continue;
      v = lower ? v.toLowerCase(Locale.ROOT) : v;
      out.add(prefix + v);
    }
    return new ArrayList<>(out);
  }

  private static double computeCapsRatio(String s) {
    int letters = 0;
    int upper = 0;
    for (int i = 0; i < s.length(); i++) {
      char c = s.charAt(i);
      if (Character.isLetter(c)) {
        letters++;
        if (Character.isUpperCase(c)) upper++;
      }
    }
    if (letters == 0) return 0.0;
    return (double) upper / (double) letters;
  }

  /*
   * Count/find occurrences of a character being repeated consecutively in a string and return the maximum run length.
   */
  private static int maxRepeatedCharRun(String s) {
    int best = 0;
    int run = 0;
    int prev = -1;
    for (int i = 0; i < s.length(); i++) {
      int c = s.charAt(i);
      if (c == prev) run++;
      else {
        run = 1;
        prev = c;
      }
      if (run > best) best = run;
    }
    return best;
  }

  private static int countEmojiCodepoints(String s) {
    int count = 0;
    for (int i = 0; i < s.length(); ) {
      int cp = s.codePointAt(i);
      // Cheap heuristic: OTHER_SYMBOL captures many emoji
      if (Character.getType(cp) == Character.OTHER_SYMBOL) count++;
      i += Character.charCount(cp);
    }
    return count;
  }
}
