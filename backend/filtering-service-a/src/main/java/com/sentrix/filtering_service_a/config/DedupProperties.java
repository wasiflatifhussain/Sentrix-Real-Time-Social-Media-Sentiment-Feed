package com.sentrix.filtering_service_a.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "app.dedup")
public class DedupProperties {
  private boolean enabled = true;
  private long ttlSeconds = 7 * 24 * 60 * 60; // 7 days
  private long bucketSeconds = 60 * 60; // 60 minutes
}
