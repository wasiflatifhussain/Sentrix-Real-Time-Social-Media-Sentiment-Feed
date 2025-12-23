package com.sentrix.filtering_service_a.pipeline.validation;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import com.sentrix.filtering_service_a.model.service_a.EventFeatures;
import com.sentrix.filtering_service_a.model.service_a.TextView;

public interface Validator {
  ValidationResult validate(IngestorEvent event, TextView textView, EventFeatures features);
}
