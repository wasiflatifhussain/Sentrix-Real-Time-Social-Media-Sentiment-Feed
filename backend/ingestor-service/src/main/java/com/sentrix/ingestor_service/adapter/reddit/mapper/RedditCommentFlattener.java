package com.sentrix.ingestor_service.adapter.reddit.mapper;

import com.sentrix.ingestor_service.adapter.reddit.model.RedditComment;
import java.util.ArrayList;
import java.util.List;
import tools.jackson.databind.JsonNode;

public class RedditCommentFlattener {
  /** Flatten Reddit comment tree JSON into a list of RedditComment objects. */
  public static List<RedditComment> flattenComments(JsonNode commentsListingJson) {
    List<RedditComment> flat = new ArrayList<>();

    if (commentsListingJson == null
        || !commentsListingJson.isArray()
        || commentsListingJson.size() < 2) {
      return flat;
    }

    // Index 1 holds the comment tree
    JsonNode commentsListing = commentsListingJson.get(1);
    JsonNode children = commentsListing.path("data").path("children");

    walk(children, flat);
    return flat;
  }

  private static void walk(JsonNode children, List<RedditComment> flat) {
    if (children == null || !children.isArray()) {
      return;
    }

    for (JsonNode node : children) {
      String kind = node.path("kind").asText("");
      JsonNode data = node.path("data");

      // Only handle actual comments
      if ("t1".equals(kind)) {
        String id = data.path("id").asText(null);
        String parentFullname = data.path("parent_id").asText(null);

        if (id == null || parentFullname == null) {
          continue;
        }

        RedditComment comment =
            RedditComment.builder()
                .id(id)
                .fullname("t1_" + id)
                .parentFullname(parentFullname)
                .author(data.path("author").asText(""))
                .body(data.path("body").asText(""))
                .score(data.hasNonNull("score") ? data.get("score").asInt() : null)
                .createdUtc(
                    data.hasNonNull("created_utc") ? data.get("created_utc").asDouble() : null)
                .build();

        flat.add(comment);

        // Recurse into replies (if present)
        JsonNode replies = data.get("replies");
        if (replies != null && replies.isObject()) {
          JsonNode replyChildren = replies.path("data").path("children");
          walk(replyChildren, flat);
        }
      }
    }
  }
}
