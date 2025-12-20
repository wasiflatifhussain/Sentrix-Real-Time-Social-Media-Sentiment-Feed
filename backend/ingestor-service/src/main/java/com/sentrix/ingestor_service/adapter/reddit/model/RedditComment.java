package com.sentrix.ingestor_service.adapter.reddit.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RedditComment {
  // Required identifiers
  private String id;
  private String fullname;

  // Threading
  private String parentFullname;

  // Content
  private String author;
  private String body;

  // Metadata
  private Integer score; // represents upvotes - downvotes

  // Reddit returns created_utc as float sometimes -> store as Double then convert later
  private Double createdUtc;
}
