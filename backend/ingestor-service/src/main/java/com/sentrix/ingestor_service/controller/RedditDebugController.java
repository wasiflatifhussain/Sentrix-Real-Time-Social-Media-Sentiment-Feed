package com.sentrix.ingestor_service.controller;

import com.sentrix.ingestor_service.adapter.reddit.RedditAdapter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

@RestController
@RequestMapping("/debug/reddit")
@RequiredArgsConstructor
public class RedditDebugController {
  private final RedditAdapter redditAdapter;

  @PostMapping("/run")
  public Mono<ResponseEntity<String>> run() {
    return Mono.fromRunnable(redditAdapter::runIngestion)
        .subscribeOn(Schedulers.boundedElastic())
        .thenReturn(ResponseEntity.ok("Triggered Reddit ingestion run."));
  }
}
