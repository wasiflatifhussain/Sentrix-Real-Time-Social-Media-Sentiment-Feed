package com.sentrix.ingestor_service.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CaptureMeta {
  private String query; // "$TSLA"
  private String sort; // "new"
  private String timeWindow; // "week"
  private String fetchedFrom; // "r/stocks" or "telegram:channel" etc.
  private String searchMode; // "search", "stream", etc. (optional)
}
