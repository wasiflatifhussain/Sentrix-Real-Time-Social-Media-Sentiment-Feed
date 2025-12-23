package com.sentrix.filtering_service_a.pipeline;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.FilteredEventEnvelope;

public interface FilteringPipeline {
  FilteredEventEnvelope process(IngestorEvent event);
}
