package com.sentrix.ingestor_service.adapter.reddit;

import com.sentrix.ingestor_service.adapter.SocialSourceAdapter;
import com.sentrix.ingestor_service.adapter.reddit.client.RedditApiClient;
import com.sentrix.ingestor_service.adapter.reddit.client.RedditAuthClient;
import com.sentrix.ingestor_service.adapter.reddit.mapper.RedditCommentFlattener;
import com.sentrix.ingestor_service.adapter.reddit.mapper.RedditEventMapper;
import com.sentrix.ingestor_service.adapter.reddit.mapper.RedditNormalizer;
import com.sentrix.ingestor_service.adapter.reddit.model.RedditComment;
import com.sentrix.ingestor_service.adapter.reddit.model.RedditPost;
import com.sentrix.ingestor_service.config.TickerConfig;
import com.sentrix.ingestor_service.config.TickerConfigLoader;
import com.sentrix.ingestor_service.messaging.producer.KafkaEventPublisher;
import com.sentrix.ingestor_service.model.CaptureMeta;
import com.sentrix.ingestor_service.model.KafkaCommentEvent;
import com.sentrix.ingestor_service.model.KafkaEvent;
import com.sentrix.ingestor_service.model.KafkaPostEvent;
import com.sentrix.ingestor_service.model.SourceType;
import com.sentrix.ingestor_service.service.DeduplicationService;
import com.sentrix.ingestor_service.service.RateLimiterRegistry;
import java.time.Instant;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class RedditAdapter implements SocialSourceAdapter {
  private static final List<String> SUBREDDITS =
      List.of("stocks", "investing", "wallstreetbets", "options");

  private final RedditAuthClient authClient;
  private final RedditApiClient apiClient;
  private final RateLimiterRegistry rateLimiterRegistry;
  private final DeduplicationService deduplicationService;
  private final TickerConfigLoader tickerConfigLoader;

  private final KafkaEventPublisher kafkaEventPublisher;
  private final ObjectMapper objectMapper;

  @Override
  public SourceType source() {
    return SourceType.REDDIT;
  }

  @Override
  public void runIngestion() {
    long ingestedAt = Instant.now().getEpochSecond();
    log.info("[RUN] Reddit ingestion start ingestedAtUtc={}", ingestedAt);

    String token = authClient.fetchAccessToken().block();
    if (token == null || token.isBlank()) {
      throw new IllegalStateException("Reddit access token is null/blank");
    }

    List<TickerConfig> tickers = tickerConfigLoader.loadTickers();

    int totalPosts = 0;
    int totalComments = 0;
    int totalDupPosts = 0;
    int totalCommentFailures = 0;
    int totalPublishFailures = 0;

    for (TickerConfig tickerConfig : tickers) {
      String ticker = tickerConfig.getTicker();
      List<String> queries = tickerConfig.getQueries();

      if (ticker == null || ticker.isBlank() || queries == null || queries.isEmpty()) {
        continue;
      }

      int tickerPosts = 0;
      int tickerComments = 0;
      int tickerDupPosts = 0;
      int tickerCommentFailures = 0;
      int tickerPublishFailures = 0;

      log.info("[START] ticker={}", ticker);

      for (String subreddit : SUBREDDITS) {
        for (String query : queries) {

          CaptureMeta capture =
              CaptureMeta.builder()
                  .query(query)
                  .sort("new")
                  .timeWindow("week")
                  .fetchedFrom("r/" + subreddit)
                  .searchMode("search")
                  .build();

          // TODO: Analyze performance trade-off to get best fit for limit between 50-75-100
          // https://www.reddit.com/dev/api/#GET_search
          // Search posts (rate-limited)
          rateLimiterRegistry.forSource(SourceType.REDDIT).acquire();
          JsonNode rawSearch =
              apiClient.searchPostsRaw(token, subreddit, query, 50, "new", "week").block();

          List<RedditPost> posts = RedditNormalizer.normalizePosts(rawSearch);
          log.info("[SEARCH] {} | r/{} | posts={}", ticker, subreddit, posts.size());

          for (RedditPost post : posts) {
            String postFullname = post.getFullname();

            // Dedup posts across ALL queries/subreddits
            if (!deduplicationService.markPostIfNew(postFullname)) {
              tickerDupPosts++;
              totalDupPosts++;
              continue;
            }

            log.info(
                "DEBUG reddit post: id={}, fullname={}, score={}, numComments={}, rawKeys?={}",
                post.getId(),
                post.getFullname(),
                post.getScore(),
                post.getNumComments(),
                post);

            // Build + publish post ingestor
            KafkaPostEvent postEvent =
                RedditEventMapper.toPostEvent(post, ticker, capture, ingestedAt);
            if (publishEvent(postEvent)) {
              tickerPosts++;
              totalPosts++;
            } else {
              tickerPublishFailures++;
              totalPublishFailures++;
            }

            // Fetch comments per post
            List<RedditComment> comments;
            try {
              rateLimiterRegistry.forSource(SourceType.REDDIT).acquire();
              JsonNode rawComments = apiClient.fetchCommentsRaw(token, post.getId(), "new").block();
              comments = RedditCommentFlattener.flattenComments(rawComments);
            } catch (Exception e) {
              tickerCommentFailures++;
              totalCommentFailures++;
              log.warn(
                  "[COMMENTS_FAIL] ticker={} postId={} reason={}",
                  ticker,
                  post.getId(),
                  e.getClass().getSimpleName());
              comments = List.of();
            }

            for (RedditComment comment : comments) {
              KafkaCommentEvent commentEvent =
                  RedditEventMapper.toCommentEvent(
                      comment, postFullname, ticker, capture, ingestedAt);

              if (publishEvent(commentEvent)) {
                tickerComments++;
                totalComments++;
              } else {
                tickerPublishFailures++;
                totalPublishFailures++;
              }
            }
          }
        }
      }

      log.info(
          "[SUMMARY] ticker={} posts={} comments={} dupPosts={} commentFailures={} publishFailures={}",
          ticker,
          tickerPosts,
          tickerComments,
          tickerDupPosts,
          tickerCommentFailures,
          tickerPublishFailures);

      log.info("[DONE] ticker={}", ticker);
    }

    log.info(
        "[RUN_DONE] posts={} comments={} dupPosts={} commentFailures={} publishFailures={}",
        totalPosts,
        totalComments,
        totalDupPosts,
        totalCommentFailures,
        totalPublishFailures);
  }

  private boolean publishEvent(Object eventObj) {
    try {
      // Use KafkaEvent base fields - safest is to serialize full object as JSON
      String json = objectMapper.writeValueAsString(eventObj);

      // Derive key/source/entityType without reflection: since base class is KafkaEvent, cast is
      // safe
      var event = (KafkaEvent) eventObj;

      kafkaEventPublisher
          .publish(
              event.getEventId(), // key
              json,
              event.getSource() != null ? event.getSource().name() : "",
              event.getEntityType() != null ? event.getEntityType().name() : "")
          .join(); // keep ingestion sequential; TODO: if need async batching ltr, change this

      return true;
    } catch (Exception e) {
      log.error("[PUBLISH_FAIL] reason={}", e.getClass().getSimpleName());
      return false;
    }
  }

  /*
   * Used for logging events in debug
   */
  private void logEvent(Object event) {
    log.info("EVENT={}", event);
  }
}
