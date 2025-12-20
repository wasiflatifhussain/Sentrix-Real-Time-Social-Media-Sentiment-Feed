package com.sentrix.ingestor_service;

import com.sentrix.ingestor_service.config.RedditConfig;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({RedditConfig.class})
public class IngestorServiceApplication {

  public static void main(String[] args) {
    SpringApplication.run(IngestorServiceApplication.class, args);
  }
}
