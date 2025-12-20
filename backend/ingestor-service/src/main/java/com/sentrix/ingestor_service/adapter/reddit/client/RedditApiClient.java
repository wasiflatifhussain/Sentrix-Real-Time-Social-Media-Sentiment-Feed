package com.sentrix.ingestor_service.adapter.reddit.client;

import com.sentrix.ingestor_service.config.RedditConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.codec.ClientCodecConfigurer;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import tools.jackson.databind.JsonNode;

@Component
@RequiredArgsConstructor
public class RedditApiClient {
  private final RedditConfig redditConfig;
  //  private final WebClient webClient = WebClient.builder().build(); // buffer not big enough
  // Default size appears is: 256KB
  private final WebClient webClient =
      WebClient.builder()
          .exchangeStrategies(
              ExchangeStrategies.builder()
                  .codecs(
                      (ClientCodecConfigurer configurer) ->
                          configurer.defaultCodecs().maxInMemorySize(4 * 1024 * 1024)) // 4MB
                  .build())
          .build();

  public Mono<JsonNode> searchPostsRaw(
      String token, String subreddit, String query, int limit, String sort, String timeFilter) {

    return webClient
        .get()
        .uri(
            uriBuilder ->
                uriBuilder
                    .scheme("https")
                    .host(stripSchemeAndHost(redditConfig.getBaseOauthUrl()))
                    .path("/r/{subreddit}/search")
                    .queryParam("q", query)
                    .queryParam("sort", sort)
                    .queryParam("limit", limit)
                    .queryParam("t", timeFilter)
                    .queryParam("restrict_sr", 1)
                    .build(subreddit))
        .header(HttpHeaders.AUTHORIZATION, "bearer " + token)
        .header(HttpHeaders.USER_AGENT, redditConfig.getUserAgent())
        .retrieve()
        .bodyToMono(JsonNode.class);
  }

  /** Returns the two-element listing array as JsonNode. */
  public Mono<JsonNode> fetchCommentsRaw(String token, String postId, String sort) {

    return webClient
        .get()
        .uri(
            uriBuilder ->
                uriBuilder
                    .scheme("https")
                    .host(stripSchemeAndHost(redditConfig.getBaseOauthUrl()))
                    .path("/comments/{postId}")
                    .queryParam("sort", sort)
                    .build(postId))
        .header(HttpHeaders.AUTHORIZATION, "bearer " + token)
        .header(HttpHeaders.USER_AGENT, redditConfig.getUserAgent())
        .retrieve()
        .bodyToMono(JsonNode.class);
  }

  /**
   * redditConfig.baseOauthUrl is a full URL; WebClient uriBuilder host expects just host. Helper to
   * support defaults.
   */
  private static String stripSchemeAndHost(String baseOauthUrl) {
    // If already host-like, return as-is
    if (!baseOauthUrl.startsWith("http")) return baseOauthUrl;
    return baseOauthUrl.replace("https://", "").replace("http://", "");
  }
}
