package com.sentrix.ingestor_service.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;

@Data
@SuperBuilder
@NoArgsConstructor
@AllArgsConstructor
public abstract class KafkaEvent {
  private Integer eventVersion;
  private SourceType source;
  private EntityType entityType;

  private String eventId;
  private String dedupKey; // same as eventId typically

  private Long createdAtUtc;
  private Long ingestedAtUtc;

  private String ticker;
  private String community; // subreddit / channel / group etc.

  private String author;
  private String title; // nullable (for posts)
  private String text; // body text

  private String contentUrl;

  private PlatformRef platform; // ids + links
  private ThreadRef thread; // null for posts, filled for comments/replies
  private EngagementMetrics metrics;

  private CaptureMeta capture; // query used to fetch this ingestor
  private String lang;
}
