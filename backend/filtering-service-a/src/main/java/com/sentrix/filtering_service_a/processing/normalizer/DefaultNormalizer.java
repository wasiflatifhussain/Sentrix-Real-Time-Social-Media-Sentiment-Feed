package com.sentrix.filtering_service_a.processing.normalizer;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.TextView;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class DefaultNormalizer implements Normalizer {

  // Standard URL pattern
  private static final Pattern URL =
      Pattern.compile("(?i)\\bhttps?://[^\\s<>\"']+|\\bwww\\.[^\\s<>\"']+");

  // Cashtag check
  private static final Pattern CASHTAG = Pattern.compile("\\$([A-Za-z]{1,10})");

  // Collapse whitespaces
  private static final Pattern MULTI_SPACE = Pattern.compile("[ \\t\\x0B\\f\\r]+");
  private static final Pattern MULTI_NEWLINE = Pattern.compile("\\n{3,}");

  @Value("${app.text.max-len:8000}")
  private int maxLen;

  @Override
  public TextView normalize(IngestorEvent event, String combinedText) {
    if (combinedText == null) {
      return TextView.builder()
          .textNormalized(null)
          .wasTruncated(false)
          .originalTextLength(0)
          .build();
    }

    int originalLen = combinedText.length();

    String s = combinedText;

    // 1) URL -> <URL>
    s = URL.matcher(s).replaceAll("<URL>");

    // 2) Cashtag normalization -> uppercase ($tsla -> $TSLA)
    s = normalizeCashtags(s);

    // 3) Whitespace cleanup
    s = s.replace('\r', '\n');
    s = MULTI_SPACE.matcher(s).replaceAll(" "); // Convert multiple spaces to single space
    s = trimLines(s); // Trim each line
    s = MULTI_NEWLINE.matcher(s).replaceAll("\n\n"); // Convert multiple newlines to double newline
    s = s.trim();

    // 4) Truncate to protect downstream
    boolean truncated = false;
    if (maxLen > 0 && s.length() > maxLen) {
      s = s.substring(0, maxLen);
      truncated = true;
    }

    return TextView.builder()
        .textNormalized(s)
        .wasTruncated(truncated)
        .originalTextLength(originalLen)
        .build();
  }

  private static String normalizeCashtags(String input) {
    Matcher m = CASHTAG.matcher(input);
    StringBuffer sb = new StringBuffer();
    while (m.find()) {
      String sym = m.group(1).toUpperCase();
      m.appendReplacement(sb, "\\$" + sym);
    }
    m.appendTail(sb);
    return sb.toString();
  }

  /*
   * Trim each line in the input string
   * Details: splits the input string by newline characters, trims whitespace from each line,
   * and then joins the lines back together with newline characters.
   */
  private static String trimLines(String s) {
    String[] lines = s.split("\n", -1);
    StringBuilder out = new StringBuilder(s.length());
    for (int i = 0; i < lines.length; i++) {
      out.append(lines[i].trim());
      if (i < lines.length - 1) out.append("\n");
    }
    return out.toString();
  }
}
