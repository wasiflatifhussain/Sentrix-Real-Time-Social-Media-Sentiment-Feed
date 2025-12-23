package com.sentrix.filtering_service_a.pipeline.dedup;

import com.sentrix.filtering_service_a.config.DedupProperties;
import com.sentrix.filtering_service_a.model.service_a.FilterReason;
import java.time.Duration;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class DedupService {
  private final RedisDedupStore store;
  private final DedupProperties props;

  // Prefixes for Redis keys - using specific format for this program
  private static final String ID_PREFIX = "dedup:id:";
  private static final String HASH_PREFIX = "dedup:hash:";

  /** Fail-open on Redis errors: if Redis is down, do NOT drop events (avoid losing data). */
  public Optional<FilterReason> checkAndMark(
      String source, String dedupKey, String textNorm, String ticker, long eventEpochSeconds) {
    if (!props.isEnabled()) return Optional.empty();

    Duration ttl = Duration.ofSeconds(props.getTtlSeconds());

    // 1) ID dedup (using existing dedupKey)
    if (dedupKey != null && !dedupKey.isBlank()) {
      String idKey = ID_PREFIX + dedupKey; // construct expected format for Redis key
      try {
        boolean first = store.firstSeen(idKey, ttl);
        if (!first) return Optional.of(FilterReason.EXACT_DUP_EVENT_ID);
      } catch (DataAccessException e) {
        log.warn("Redis error during ID dedup (fail-open). key={}", idKey, e);
      }
    }

    // 2) Content hash dedup
    String src = (source == null) ? "" : source.trim();
    String tn = (textNorm == null) ? "" : textNorm;
    String tk = (ticker == null) ? "" : ticker.trim().toUpperCase();

    long bucketSeconds = Math.max(1, props.getBucketSeconds());
    long bucket = Math.floorDiv(eventEpochSeconds, bucketSeconds);

    // Reason for using bucket: detect duplicates for a ticker across the various queries within a
    // time window
    String toHash = src + "|" + tn + "|" + tk + "|" + bucket; // construct fix format for hashing
    String hash = Sha256Hasher.hex(toHash); // compute SHA-256 hash in hex format

    String hashKey = HASH_PREFIX + hash;
    try {
      boolean first = store.firstSeen(hashKey, ttl);
      if (!first) return Optional.of(FilterReason.EXACT_DUP_CONTENT);
    } catch (DataAccessException e) {
      log.warn("Redis error during content-hash dedup (fail-open). key={}", hashKey, e);
    }

    return Optional.empty();
  }
}
