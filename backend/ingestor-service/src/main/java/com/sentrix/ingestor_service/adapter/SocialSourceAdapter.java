package com.sentrix.ingestor_service.adapter;

import com.sentrix.ingestor_service.model.event.SourceType;

/**
 * Common interface for all social ingestion adapters.
 *
 * <p>Each implementation represents one data source (e.g. Reddit, Twitter, Telegram).
 *
 * <p>Adapters are discovered automatically by the orchestrator and executed concurrently during
 * ingestion runs.
 */
public interface SocialSourceAdapter {
  SourceType source();

  void runIngestion();
}
