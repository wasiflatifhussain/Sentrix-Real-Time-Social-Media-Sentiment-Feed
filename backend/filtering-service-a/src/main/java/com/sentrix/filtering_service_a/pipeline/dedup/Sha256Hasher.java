package com.sentrix.filtering_service_a.pipeline.dedup;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/*
 * Hashes a string using SHA-256 and returns the hex representation of the hash in string format for Redis storage.
 */
public final class Sha256Hasher {
  private Sha256Hasher() {}

  public static String hex(String s) {
    try {
      MessageDigest md = MessageDigest.getInstance("SHA-256");
      byte[] digest =
          md.digest(
              s.getBytes(
                  StandardCharsets.UTF_8)); // gets string bytes and hashes them to fixed length
      // 32-byte array
      StringBuilder sb =
          new StringBuilder(
              digest.length
                  * 2); // each byte = 8 bits; each hex char = 4 bits; so, 2 hex chars per byte
      for (byte b : digest) sb.append(String.format("%02x", b)); // convert byte to hex
      return sb.toString();
    } catch (NoSuchAlgorithmException e) {
      throw new IllegalStateException("SHA-256 not available", e);
    }
  }
}
