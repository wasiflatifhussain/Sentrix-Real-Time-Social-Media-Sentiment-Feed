package com.sentrix.filtering_service_a.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "app.event-feature-checks")
public class EventFeatureChecksPropertiesConfig {
  private boolean enabled = true;

  private UrlSpam urlSpam = new UrlSpam();
  private Emoji emoji = new Emoji();
  private RepeatChar repeatChar = new RepeatChar();
  private Cashtag cashtag = new Cashtag();

  @Data
  public static class UrlSpam {
    private int hardDropCount = 6;
    private int shortTextDropCount = 3;
    private int shortTextMaxWords = 8;
  }

  @Data
  public static class Emoji {
    private int hardDropCount = 20;
    private int shortTextDropCount = 10;
    private int shortTextMaxWords = 6;
  }

  @Data
  public static class RepeatChar {
    private int hardRunLen = 12;
  }

  @Data
  public static class Cashtag {
    private int hardDropCount = 12;
    private int shortTextDropCount = 6;
    private int shortTextMaxWords = 12;
  }
}
