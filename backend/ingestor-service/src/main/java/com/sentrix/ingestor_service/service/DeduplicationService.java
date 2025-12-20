package com.sentrix.ingestor_service.service;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Service;

@Service
public class DeduplicationService {
  private final Set<String> seenPostFullnames = ConcurrentHashMap.newKeySet();

  /**
   * @return true if this post fullname has NOT been seen before (and is now marked seen). false if
   *     it was already seen.
   */
  public boolean markPostIfNew(String postFullname) {
    if (postFullname == null || postFullname.isBlank()) {
      return false;
    }
    return seenPostFullnames.add(postFullname);
  }

  public int seenPostCount() {
    return seenPostFullnames.size();
  }

  public void clearPosts() {
    seenPostFullnames.clear();
  }
}
