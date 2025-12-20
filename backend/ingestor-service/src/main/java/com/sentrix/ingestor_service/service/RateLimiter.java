package com.sentrix.ingestor_service.service;

import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class RateLimiter {
  private final long callIntervalMillis;
  private final Lock lock = new ReentrantLock();
  private long lastCallAtMillis = 0L;

  public RateLimiter(int maxCallsPerMinute) {
    if (maxCallsPerMinute <= 0) {
      throw new IllegalArgumentException("maxCallsPerMinute must be > 0");
    }
    this.callIntervalMillis = Math.round(60_000.0 / maxCallsPerMinute);
  }

  public void acquire() {
    lock.lock();
    try {
      long now = System.currentTimeMillis();
      long elapsed = now - lastCallAtMillis;

      if (elapsed < callIntervalMillis) {
        long sleepMs = callIntervalMillis - elapsed;
        try {
          Thread.sleep(sleepMs);
        } catch (InterruptedException e) {
          Thread.currentThread().interrupt();
        }
      }

      lastCallAtMillis = System.currentTimeMillis();
    } finally {
      lock.unlock();
    }
  }
}
