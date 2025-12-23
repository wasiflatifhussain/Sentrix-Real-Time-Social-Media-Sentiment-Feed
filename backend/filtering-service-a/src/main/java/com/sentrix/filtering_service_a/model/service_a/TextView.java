package com.sentrix.filtering_service_a.model.service_a;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class TextView {
  private String textNormalized; // title + body combined, normalized (eg: lowercased)
  private boolean wasTruncated;
  private int originalTextLength;
}
