package com.sentrix.filtering_service_a.pipeline.near_dup_detect;

import java.nio.charset.StandardCharsets;

/**
 * Computes a 64-bit SimHash fingerprint from text.
 *
 * <p>Idea: - Split text into tokens. - Hash each token into 64 bits. - Maintain a 64-dim
 * accumulator vector: +1 for a token's 1-bit, -1 for a 0-bit. - Final fingerprint bit i is 1 if
 * accumulator[i] >= 0, else 0.
 *
 * <p>Property: Similar texts (sharing many tokens) tend to produce fingerprints with small Hamming
 * distance.
 */
public class SimHash64 {

  private static final int BITS = 64;

  private SimHash64() {}

  /** Returns the 64-bit fingerprint for the given (normalized) text. */
  public static long fingerprint(String text) {
    if (text == null || text.isBlank()) return 0L;

    int[] vec = new int[BITS];

    for (String token : text.split("\\s+")) {
      if (token.length() < 3) continue;

      long hash = tokenHash64(token);
      for (int i = 0; i < BITS; i++) {
        if (((hash >>> i) & 1L) == 1L) vec[i] += 1;
        else vec[i] -= 1;
      }
    }

    long fingerprint = 0L;
    for (int i = 0; i < BITS; i++) {
      if (vec[i] >= 0) fingerprint |= (1L << i);
    }
    return fingerprint;
  }

  /**
   * A small fast 64-bit token hash. This is FNV-1a style (good enough for token hashing in
   * SimHash).
   */
  private static long tokenHash64(String s) {
    byte[] data = s.getBytes(StandardCharsets.UTF_8);
    long hashAcccumulator = 0xcbf29ce484222325L;
    for (byte b : data) {
      hashAcccumulator ^= b;
      hashAcccumulator *= 0x100000001b3L;
    }
    return hashAcccumulator;
  }
}
