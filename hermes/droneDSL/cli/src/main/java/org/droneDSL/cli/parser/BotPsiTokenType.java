package org.droneDSL.cli.parser;

import com.intellij.psi.tree.IElementType;
import org.droneDSL.cli.psi.BotLanguage;

public class BotPsiTokenType extends IElementType {
  public BotPsiTokenType(String plus) {
    super(plus, BotLanguage.INSTANCE);
  }
}
