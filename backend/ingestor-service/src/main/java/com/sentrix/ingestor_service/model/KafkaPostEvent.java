package com.sentrix.ingestor_service.model;

import lombok.EqualsAndHashCode;
import lombok.ToString;
import lombok.experimental.SuperBuilder;

/**
 * Marker subclass for Reddit POST/COMMENT events.
 *
 * <p>Design notes: - No @Data: this class declares no fields; all state lives in the KafkaEvent
 * base class. Adding @Data here would generate redundant methods and a misleading toString().
 *
 * <p>- @SuperBuilder: required to correctly build this subclass while setting fields defined in the
 * superclass (KafkaEvent). Regular @Builder does not work with inheritance.
 *
 * <p>- @EqualsAndHashCode(callSuper = true): ensures equality and hash code include all KafkaEvent
 * fields, which is important for deduplication and comparisons.
 *
 * <p>- @ToString(callSuper = true): includes superclass fields in logs; without this, logs would
 * appear empty (e.g. KafkaPostEvent()).
 *
 * <p>- No no-args or all-args constructors: these are provided by the superclass's @SuperBuilder.
 */
@SuperBuilder
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
public class KafkaPostEvent extends KafkaEvent {
  // No additional fields for now - all are inherited from KafkaEvent
}
