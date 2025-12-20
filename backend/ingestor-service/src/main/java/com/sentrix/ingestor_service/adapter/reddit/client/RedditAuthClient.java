package com.sentrix.ingestor_service.adapter.reddit.client;

import com.sentrix.ingestor_service.config.RedditConfig;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ClientCodecConfigurer;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import tools.jackson.databind.JsonNode;

@Component
@RequiredArgsConstructor
public class RedditAuthClient {
  private final RedditConfig redditConfig;
  //  private final WebClient webClient = WebClient.builder().build(); // buffer not big enough
  private final WebClient webClient =
      WebClient.builder()
          .exchangeStrategies(
              ExchangeStrategies.builder()
                  .codecs(
                      (ClientCodecConfigurer configurer) ->
                          configurer.defaultCodecs().maxInMemorySize(4 * 1024 * 1024)) // 4MB
                  .build())
          .build();

  /**
   * Fetch OAuth2 access token using "password" grant (script app), matching your Python
   * get_access_token().
   */
  public Mono<String> fetchAccessToken() {
    String basic = basicAuth(redditConfig.getClientId(), redditConfig.getClientSecret());

    return webClient
        .post()
        .uri(redditConfig.getTokenUrl())
        .header(HttpHeaders.AUTHORIZATION, "Basic " + basic)
        .header(HttpHeaders.USER_AGENT, redditConfig.getUserAgent())
        .contentType(MediaType.APPLICATION_FORM_URLENCODED)
        .body(
            BodyInserters.fromFormData("grant_type", "password")
                .with("username", redditConfig.getUsername())
                .with("password", redditConfig.getPassword()))
        .retrieve()
        .bodyToMono(JsonNode.class)
        .map(
            json -> {
              JsonNode token = json.get("access_token");
              if (token == null || token.isNull()) {
                throw new IllegalStateException("Reddit token response missing access_token");
              }
              return token.asText();
            });
  }

  private static String basicAuth(String clientId, String clientSecret) {
    String raw = clientId + ":" + clientSecret;
    return Base64.getEncoder().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
  }
}
