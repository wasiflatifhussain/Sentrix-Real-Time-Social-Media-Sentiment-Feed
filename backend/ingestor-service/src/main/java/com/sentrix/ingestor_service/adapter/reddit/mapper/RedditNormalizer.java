package com.sentrix.ingestor_service.adapter.reddit.mapper;

import com.sentrix.ingestor_service.adapter.reddit.model.RedditPost;
import java.util.ArrayList;
import java.util.List;
import tools.jackson.databind.JsonNode;

public class RedditNormalizer {

  /** Convert Reddit search listing JSON into a list of normalized RedditPost objects. */
  public static List<RedditPost> normalizePosts(JsonNode searchJson) {
    List<RedditPost> posts = new ArrayList<>();

    if (searchJson == null) {
      return posts;
    }

    JsonNode children = searchJson.path("data").path("children");

    if (!children.isArray()) {
      return posts;
    }

    for (JsonNode child : children) {
      JsonNode data = child.path("data");

      String id = data.path("id").asText(null);
      String fullname = data.path("name").asText(null);

      if (id == null || fullname == null) {
        continue;
      }

      RedditPost post =
          RedditPost.builder()
              .id(id)
              .fullname(fullname)
              .subreddit(data.path("subreddit").asText(""))
              .title(data.path("title").asText(""))
              .selftext(data.path("selftext").asText(""))
              .url(data.path("url").asText(""))
              .permalink(data.path("permalink").asText(""))
              .author(data.path("author").asText(""))
              .score(data.hasNonNull("score") ? data.get("score").asInt() : null)
              .createdUtc(
                  data.hasNonNull("created_utc") ? data.get("created_utc").asDouble() : null)
              .build();

      posts.add(post);
    }

    return posts;
  }
}
