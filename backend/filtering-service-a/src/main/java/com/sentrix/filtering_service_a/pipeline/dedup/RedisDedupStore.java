package com.sentrix.filtering_service_a.pipeline.dedup;

import java.time.Duration;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class RedisDedupStore {
  private final StringRedisTemplate redis;

  /**
   * @return true if the key was absent and is now stored (first time seen), false if it already
   *     existed.
   */
  public boolean firstSeen(String key, Duration ttl) throws DataAccessException {
    Boolean ok = redis.opsForValue().setIfAbsent(key, "1", ttl);
    return Boolean.TRUE.equals(ok);
  }
}
