package com.sentrix.ingestor_service.adapter.reddit.mapper;

import com.sentrix.ingestor_service.adapter.reddit.model.RedditComment;
import com.sentrix.ingestor_service.adapter.reddit.model.RedditPost;
import com.sentrix.ingestor_service.model.*;
import java.time.Instant;
import java.util.Objects;

/*
 * Contains static methods to map Reddit-specific data to generic ingestor structures
 */
public class RedditEventMapper {
  private static final int EVENT_VERSION = 1;

  private RedditEventMapper() {}

  public static KafkaPostEvent toPostEvent(
          RedditPost post, String ticker, CaptureMeta capture, Long ingestedAtUtc) {
    Objects.requireNonNull(post, "post must not be null");
    Objects.requireNonNull(ticker, "ticker must not be null");

    long ingested = (ingestedAtUtc != null) ? ingestedAtUtc : nowEpochSeconds();
    Long created = toLongEpochSeconds(post.getCreatedUtc());

    String postFullname = post.getFullname();
    String eventId = "reddit:" + postFullname;

    PlatformRef platform =
        PlatformRef.builder()
            .id(post.getId())
            .fullName(postFullname)
            .permalink(post.getPermalink())
            .rawUrl(post.getUrl())
            .build();

    EngagementMetrics metrics =
        EngagementMetrics.builder()
            .likeCount(post.getScore() != null ? post.getScore().longValue() : null)
            .build();

    return KafkaPostEvent.builder()
        .eventVersion(EVENT_VERSION)
        .source(SourceType.REDDIT)
        .entityType(EntityType.POST)
        .eventId(eventId)
        .dedupKey(eventId)
        .createdAtUtc(created)
        .ingestedAtUtc(ingested)
        .ticker(ticker)
        .community(nullToEmpty(post.getSubreddit()))
        .author(nullToEmpty(post.getAuthor()))
        .title(nullToEmpty(post.getTitle()))
        .text(nullToEmpty(post.getSelftext()))
        .contentUrl(post.getUrl())
        .platform(platform)
        .thread(null) // posts have no thread object
        .metrics(metrics)
        .capture(capture)
        .lang(null)
        .build();
  }

  public static KafkaCommentEvent toCommentEvent(
      RedditComment comment,
      String rootPostFullname,
      String ticker,
      CaptureMeta capture,
      Long ingestedAtUtc) {
    Objects.requireNonNull(comment, "comment must not be null");
    Objects.requireNonNull(rootPostFullname, "rootPostFullname must not be null");
    Objects.requireNonNull(ticker, "ticker must not be null");

    long ingested = (ingestedAtUtc != null) ? ingestedAtUtc : nowEpochSeconds();
    Long created = toLongEpochSeconds(comment.getCreatedUtc());

    String commentFullname = comment.getFullname(); // t1_xxx
    String eventId = "reddit:" + commentFullname;

    PlatformRef platform =
        PlatformRef.builder()
            .id(comment.getId())
            .fullName(commentFullname)
            .permalink(null) // matches your Python: permalink ""
            .rawUrl(null) // matches your Python: url ""
            .build();

    ThreadRef thread =
        ThreadRef.builder()
            .rootId(rootPostFullname)
            .parentId(comment.getParentFullname())
            .conversationId(null)
            .build();

    EngagementMetrics metrics =
        EngagementMetrics.builder()
            .likeCount(comment.getScore() != null ? comment.getScore().longValue() : null)
            .build();

    return KafkaCommentEvent.builder()
        .eventVersion(EVENT_VERSION)
        .source(SourceType.REDDIT)
        .entityType(EntityType.COMMENT)
        .eventId(eventId)
        .dedupKey(eventId)
        .createdAtUtc(created)
        .ingestedAtUtc(ingested)
        .ticker(ticker)
        .community(extractCommunityFromCapture(capture))
        .author(nullToEmpty(comment.getAuthor()))
        .title(null) // comments have no title
        .text(nullToEmpty(comment.getBody()))
        .contentUrl(null)
        .platform(platform)
        .thread(thread)
        .metrics(metrics)
        .capture(capture)
        .lang(null)
        .build();
  }

  //  --- Helper methods ---

  private static long nowEpochSeconds() {
    return Instant.now().getEpochSecond();
  }

  private static Long toLongEpochSeconds(Double maybeEpochSeconds) {
    if (maybeEpochSeconds == null) return null;
    return (long) Math.floor(maybeEpochSeconds);
  }

  private static String nullToEmpty(String s) {
    return (s == null) ? "" : s;
  }

  private static String extractCommunityFromCapture(CaptureMeta capture) {
    if (capture == null) return "";
    String fetchedFrom = capture.getFetchedFrom();
    if (fetchedFrom == null) return "";
    if (fetchedFrom.startsWith("r/")) return fetchedFrom.substring(2);
    return fetchedFrom;
  }
}
