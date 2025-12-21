package com.sentrix.ingestor_service.service;

import com.sentrix.ingestor_service.model.SourceType;
import java.util.EnumMap;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class RateLimiterRegistry {

  private final Map<SourceType, RateLimiter> bySource = new EnumMap<>(SourceType.class);

  public RateLimiterRegistry() {
    bySource.put(SourceType.REDDIT, new RateLimiter(100));
    bySource.put(SourceType.TWITTER, new RateLimiter(60));
    bySource.put(SourceType.TELEGRAM, new RateLimiter(120));
  }

  public RateLimiter forSource(SourceType source) {
    RateLimiter limiter = bySource.get(source);
    if (limiter == null) {
      throw new IllegalArgumentException("No rate limiter configured for source=" + source);
    }
    return limiter;
  }
}
