package com.sentrix.filtering_service_a.pipeline.features;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.EventFeatures;
import com.sentrix.filtering_service_a.model.service_a.TextView;

public interface FeatureExtractor {
  EventFeatures extract(IngestorEvent ingestorEvent, TextView normalizedText);
}
