package org.droneDSL.cli.parser;

import com.intellij.psi.tree.IElementType;
import org.droneDSL.cli.psi.BotLanguage;

public class BotPsiElementType extends IElementType {
  public BotPsiElementType(String plus) {
    super(plus, BotLanguage.INSTANCE);
  }
}
