package com.sentrix.filtering_service_a.model.ingestor;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class ThreadRef {
  private String rootId; // e.g. root post fullname or root tweet id
  private String parentId; // e.g. parent comment fullname / in-reply-to id
  private String conversationId; // optional (useful for Twitter later)
}
