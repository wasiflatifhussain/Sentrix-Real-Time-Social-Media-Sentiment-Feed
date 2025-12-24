package com.sentrix.filtering_service_a.model.service_a;

import java.util.List;
import java.util.Map;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class FilterMeta {
  private String filterStage; // eg: service-A, service-B
  private Decision decision;

  private FilterReason filterReason;
  private Long processedAtUtc; // all timestamps are epoch seconds UTC

  private List<String> tags;
  private Map<String, Object> signals;
}
