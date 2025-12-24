package com.sentrix.filtering_service_a.pipeline.near_dup_detect;

import com.sentrix.filtering_service_a.config.NearDupConfig;
import java.time.Duration;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

/**
 * Phase 6 service: detects near-duplicate "waves" within a short rolling window.
 *
 * <p>Storage model (Redis): - Key: neardup:{source}:{ticker}:{bucket} - Value: SET of 64-bit
 * fingerprints (stored as unsigned decimal strings) - TTL: short (e.g., 1 hour) to bound memory and
 * keep comparisons local
 *
 * <p>Workflow: 1) Load recent fingerprints for the scope (source, ticker, time bucket [and
 * optionally previous bucket]). 2) Compare current fingerprint to each stored fingerprint using
 * Hamming distance. 3) Count near-matches (distance <= maxHamming). 4) Record current fingerprint
 * into the bucket set and set TTL. 5) Return a NearDupResult used for tagging (KEEP only).
 */
@Service
@RequiredArgsConstructor
public class NearDupService {

  private final StringRedisTemplate redis;
  private final NearDupConfig nearDupConfig;

  public NearDupResult checkAndRecord(
      String source, String ticker, long fingerPrint, long nowEpochSec) {
    if (source == null) source = "";
    if (ticker == null) ticker = "";

    long bucket = nowEpochSec / nearDupConfig.getBucketSeconds();

    int matches = 0;
    int minHam = Integer.MAX_VALUE;

    // Check current bucket
    ResultAgg agg1 = compareAgainstBucket(source, ticker, bucket, fingerPrint);
    matches += agg1.matches;
    minHam = Math.min(minHam, agg1.minHam);

    // Check previous bucket to reduce edge effects at bucket boundaries
    if (nearDupConfig.isCheckPrevBucket()) {
      ResultAgg agg2 = compareAgainstBucket(source, ticker, bucket - 1, fingerPrint);
      matches += agg2.matches;
      minHam = Math.min(minHam, agg2.minHam);
    }

    // Record into current bucket
    String key = redisKey(source, ticker, bucket);
    redis.opsForSet().add(key, Long.toUnsignedString(fingerPrint));
    redis.expire(key, Duration.ofSeconds(nearDupConfig.getTtlSeconds()));

    boolean wave = matches >= nearDupConfig.getMinMatches();
    return NearDupResult.builder()
        .nearDupWave(wave)
        .matchCount(matches)
        .minHamming(minHam == Integer.MAX_VALUE ? -1 : minHam)
        .build();
  }

  /*
   * Compare the given fingerprint against all stored fingerprints in the specified bucket.
   * Returns the number of matches within maxHamming distance and the minimum Hamming distance found.
   */
  private ResultAgg compareAgainstBucket(String source, String ticker, long bucket, long fp) {
    String key = redisKey(source, ticker, bucket);
    Set<String> existing = redis.opsForSet().members(key);

    int matches = 0;
    int minHam = Integer.MAX_VALUE;

    if (existing != null) {
      for (String s : existing) {
        long prev = Long.parseUnsignedLong(s);
        int distance = Hamming.dist(fp, prev);
        minHam = Math.min(minHam, distance);
        if (distance <= nearDupConfig.getMaxHamming()) matches++;
      }
    }
    return new ResultAgg(matches, minHam);
  }

  private String redisKey(String source, String ticker, long bucket) {
    return "neardup:" + source + ":" + ticker + ":" + bucket;
  }

  private record ResultAgg(int matches, int minHam) {}
}
