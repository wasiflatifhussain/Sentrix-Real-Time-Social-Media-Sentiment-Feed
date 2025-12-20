package com.sentrix.ingestor_service.orchestrator;

import com.sentrix.ingestor_service.adapter.SocialSourceAdapter;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicBoolean;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

/**
 * Coordinates ingestion across all social data sources.
 *
 * <p>Responsibilities: - Discover all SocialSourceAdapter implementations
 *
 * <p>Run each adapter concurrently using a shared thread pool - Prevent overlapping ingestion runs
 *
 * <p>Provide a single orchestration point for scheduling and execution
 *
 * <p>This class centralizes concurrency control and lifecycle management for ingestion runs.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class IngestionOrchestrator {
  private final List<SocialSourceAdapter>
      adapters; // Spring injects all SocialSourceAdapter implementations
  private final @Qualifier("ingestionExecutor") Executor ingestionExecutor;

  // prevents overlap if a run takes longer than an hour
  private final AtomicBoolean running = new AtomicBoolean(false);

  public void runAllIngestions() {
    if (!running.compareAndSet(false, true)) {
      log.warn("[ORCH] Previous ingestion run still active - skipping this schedule tick.");
      return;
    }

    long start = System.currentTimeMillis();
    log.info("[ORCH] Ingestion run start adapters={}", adapters.size());

    try {
      List<CompletableFuture<Void>> futures =
          adapters.stream()
              .map(
                  adapter ->
                      CompletableFuture.runAsync(() -> runIngestion(adapter), ingestionExecutor)
                          .orTimeout(
                              Duration.ofMinutes(55).toSeconds(),
                              java.util.concurrent.TimeUnit.SECONDS)
                          .exceptionally(
                              ex -> {
                                log.error(
                                    "[ORCH] adapter={} failed err={}",
                                    adapter.source(),
                                    ex.toString());
                                return null;
                              }))
              .toList();

      CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

      long ms = System.currentTimeMillis() - start;
      log.info("[ORCH] Ingestion run done durationMs={}", ms);

    } finally {
      running.set(false);
    }
  }

  private void runIngestion(SocialSourceAdapter adapter) {
    long start = System.currentTimeMillis();
    log.info("[ORCH] adapter={} start", adapter.source());
    adapter.runIngestion();
    long ms = System.currentTimeMillis() - start;
    log.info("[ORCH] adapter={} done durationMs={}", adapter.source(), ms);
  }
}
