package com.sentrix.filtering_service_a.model.service_a;

import com.sentrix.filtering_service_a.model.ingestor.IngestorEvent;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FilteredEventEnvelope {
  private IngestorEvent ingestorEvent;

  private FilterMeta filterMeta;
  private TextView textView;
  private EventFeatures eventFeatures;
}
