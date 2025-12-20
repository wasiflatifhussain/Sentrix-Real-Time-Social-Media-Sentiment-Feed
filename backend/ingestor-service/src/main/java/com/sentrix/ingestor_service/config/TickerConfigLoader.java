package com.sentrix.ingestor_service.config;

import java.io.InputStream;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Component
@RequiredArgsConstructor
public class TickerConfigLoader {

  private final ObjectMapper objectMapper;

  public List<TickerConfig> loadTickers() {
    try (InputStream is = new ClassPathResource("tickers.json").getInputStream()) {

      return objectMapper.readValue(is, new TypeReference<List<TickerConfig>>() {});

    } catch (Exception e) {
      throw new IllegalStateException("Failed to load tickers.json from classpath", e);
    }
  }
}
