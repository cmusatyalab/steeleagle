package org.droneDSL.compile.psi;

import com.intellij.lang.Language;
import org.jetbrains.annotations.NotNull;

public final class BotLanguage extends Language {
  public static final @NotNull BotLanguage INSTANCE = new BotLanguage();

  private BotLanguage() {
    super("Bot");
  }
}
