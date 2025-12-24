package com.sentrix.filtering_service_a.pipeline.near_dup_detect;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Result of a near-duplicate check in Phase 6.
 *
 * <p>nearDupWave: true if we found enough near-matches within the configured threshold/window
 * matchCount: number of fingerprints within maxHamming distance minHamming: smallest distance
 * observed among compared fingerprints (lower = more similar)
 */
@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class NearDupResult {
  private boolean nearDupWave;
  private int matchCount;
  private int minHamming;
}
