package com.sentrix.ingestor_service.adapter.reddit.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RedditPost {
  // Required identifiers
  private String id;
  private String fullname;

  // Content/context
  private String subreddit;
  private String title;
  private String selftext;
  private String url;
  private String permalink;

  // Metadata
  private String author;
  private Integer score;

  private Integer numComments;

  // Reddit returns created_utc as float sometimes -> store as Double then convert later
  private Double createdUtc;
}
