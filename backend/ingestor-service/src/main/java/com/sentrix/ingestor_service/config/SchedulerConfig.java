package com.sentrix.ingestor_service.config;

import java.util.concurrent.Executor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

@Configuration
@EnableScheduling
public class SchedulerConfig {

  /**
   * Thread pool for concurrent ingestion execution.
   *
   * <p>Core pool size matches the expected number of social platforms (Reddit, Twitter, Telegram).
   *
   * <p>This executor is intentionally separate from Spring's scheduler thread pool.
   */
  @Bean(name = "ingestionExecutor")
  public Executor ingestionExecutor() {
    ThreadPoolTaskExecutor threadPoolTaskExecutor = new ThreadPoolTaskExecutor();
    threadPoolTaskExecutor.setCorePoolSize(3); // reddit + twitter + telegram
    threadPoolTaskExecutor.setMaxPoolSize(6);
    threadPoolTaskExecutor.setQueueCapacity(50);
    threadPoolTaskExecutor.setThreadNamePrefix("ingestion-");
    threadPoolTaskExecutor.initialize();
    return threadPoolTaskExecutor;
  }
}
