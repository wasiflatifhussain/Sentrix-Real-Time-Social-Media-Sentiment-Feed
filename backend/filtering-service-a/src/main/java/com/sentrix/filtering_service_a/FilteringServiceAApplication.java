package com.sentrix.filtering_service_a;

import com.sentrix.filtering_service_a.config.DedupProperties;
import com.sentrix.filtering_service_a.config.EventFeatureChecksPropertiesConfig;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

@SpringBootApplication
@EnableConfigurationProperties({DedupProperties.class, EventFeatureChecksPropertiesConfig.class})
public class FilteringServiceAApplication {

  public static void main(String[] args) {
    SpringApplication.run(FilteringServiceAApplication.class, args);
  }
}
