package com.sentrix.filtering_service_a.pipeline.normalizer;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.TextView;

public interface Normalizer {
  TextView normalize(IngestorEvent event, String combinedText);
}
