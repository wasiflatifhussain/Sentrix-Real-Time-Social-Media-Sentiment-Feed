package com.sentrix.ingestor_service.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class PlatformRef {
  private String id; // e.g. "1ppy447" or tweetId or telegram messageId
  private SourceType platformType;
  private String fullName; // e.g. "t3_1ppy447" (Reddit only)
  private String permalink; // e.g. "/r/stocks/comments/..."
  private String rawUrl;
}
