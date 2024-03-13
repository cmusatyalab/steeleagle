package org.droneDSL.compile.parser;

import com.intellij.psi.tree.IElementType;
import org.droneDSL.compile.psi.BotLanguage;

public class BotPsiElementType extends IElementType {
  public BotPsiElementType(String plus) {
    super(plus, BotLanguage.INSTANCE);
  }
}
