package com.sentrix.ingestor_service.config;

import java.util.List;
import lombok.Data;

@Data
public class TickerConfig {
  private String ticker;
  private List<String> queries;
}
