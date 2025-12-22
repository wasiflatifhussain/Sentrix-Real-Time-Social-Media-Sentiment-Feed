package com.sentrix.filtering_service_a.processing.validation;

import com.sentrix.filtering_service_a.model.service_a.FilterReason;
import lombok.Builder;
import lombok.Value;

/*
 * This method does not have private variables and also has static methods to create instances.
 * Reason for static methods and no setters is to make the class immutable.
 * This ensures that once a ValidationResult object is created, its state cannot be changed.
 * This immutability is crucial for thread safety, as it prevents concurrent threads from modifying the
 * object's state, which could lead to inconsistent or unpredictable behavior.
 * By using static factory methods (ok and drop), it can clearly define the two possible states of the
 * ValidationResult: a successful validation (ok) and a failed validation (drop). And prevent successful
 * validation from having a reason.
 */
@Value
@Builder
public class ValidationResult {
  boolean ok;
  FilterReason reason;

  public static ValidationResult ok() {
    return ValidationResult.builder().ok(true).reason(null).build();
  }

  public static ValidationResult drop(FilterReason reason) {
    return ValidationResult.builder().ok(false).reason(reason).build();
  }
}
