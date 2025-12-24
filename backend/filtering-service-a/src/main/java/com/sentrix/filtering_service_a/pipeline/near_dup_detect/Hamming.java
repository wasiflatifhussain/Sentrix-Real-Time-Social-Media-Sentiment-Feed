package com.sentrix.filtering_service_a.pipeline.near_dup_detect;

/**
 * Utility for computing Hamming distance between two 64-bit fingerprints.
 *
 * <p>Hamming distance = number of bit positions that differ. Implementation: - XOR -> bits that
 * differ become 1 - bitCount -> counts the 1s
 */
public class Hamming {
  private Hamming() {}

  public static int dist(long a, long b) {
    return Long.bitCount(a ^ b);
  }
}
