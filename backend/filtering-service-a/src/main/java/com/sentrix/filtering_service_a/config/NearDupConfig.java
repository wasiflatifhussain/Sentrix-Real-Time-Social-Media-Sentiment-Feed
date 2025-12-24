package com.sentrix.filtering_service_a.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "app.neardup")
public class NearDupConfig {
  private boolean enabled = true;
  private int minWords = 30;
  private int maxHamming = 5;
  private int minMatches = 3;
  private int bucketSeconds = 900;
  private int ttlSeconds = 3600;
  private boolean checkPrevBucket = true;
}
