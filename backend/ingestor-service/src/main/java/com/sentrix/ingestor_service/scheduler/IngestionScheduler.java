package com.sentrix.ingestor_service.scheduler;

import com.sentrix.ingestor_service.orchestrator.IngestionOrchestrator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Triggers periodic ingestion runs using Spring's scheduler.
 *
 * <p>This scheduler is responsible only for *when* ingestion runs. It does NOT perform ingestion
 * logic itself.
 *
 * <p>- Runs once per hour (top of the hour) - Delegates execution to IngestionOrchestrator -
 * Concurrency and overlap control are handled downstream
 *
 * <p>In production, this can be replaced or supplemented with an external scheduler (e.g.
 * Kubernetes CronJob).
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class IngestionScheduler {
  private final IngestionOrchestrator ingestionOrchestrator;

  @Scheduled(
      cron = "${ingestion.scheduler.cron:0 0 * * * *}",
      zone =
          "${ingestion.scheduler.zone:UTC}")
  public void scheduleIngestionRun() {
    log.info("[SCHED] Triggering scheduled ingestion run.");
    ingestionOrchestrator.runAllIngestions();
  }
}
