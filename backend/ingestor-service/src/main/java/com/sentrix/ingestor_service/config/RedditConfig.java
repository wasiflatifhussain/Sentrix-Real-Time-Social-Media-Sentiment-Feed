package com.sentrix.ingestor_service.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "reddit")
public class RedditConfig {
  private String clientId;
  private String clientSecret;
  private String username;
  private String password;

  // Defaults
  private String tokenUrl = "https://www.reddit.com/api/v1/access_token";
  private String baseOauthUrl = "https://oauth.reddit.com";

  // User agent needed for Reddit
  private String userAgent = "sentrix-ingestor/0.1 by unknown";
}
