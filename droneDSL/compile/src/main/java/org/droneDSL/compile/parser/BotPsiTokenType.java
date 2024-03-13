package org.droneDSL.compile.parser;

import com.intellij.psi.tree.IElementType;
import org.droneDSL.compile.psi.BotLanguage;

public class BotPsiTokenType extends IElementType {
  public BotPsiTokenType(String plus) {
    super(plus, BotLanguage.INSTANCE);
  }
}
