package com.sentrix.ingestor_service.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EngagementMetrics {
  private Long likeCount; // reddit score here
  private Long replyCount;
  private Long shareCount;
  private Long viewCount;
  private Long commentCount;
}
