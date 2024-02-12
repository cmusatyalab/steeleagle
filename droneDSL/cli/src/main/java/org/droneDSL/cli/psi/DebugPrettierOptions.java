package org.droneDSL.cli.psi;

import org.aya.util.prettier.PrettierOptions;
import org.jetbrains.annotations.NotNull;

// TODO: use better one
public class DebugPrettierOptions extends PrettierOptions {
  public DebugPrettierOptions(@NotNull Class<?> keyClass) {
    super(keyClass);
  }

  public DebugPrettierOptions() {
    this(DebugPrettierOptions.class);
  }

  @Override public void reset() {
    map.clear();
  }
}