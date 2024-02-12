package org.droneDSL.cli.psi;

import com.intellij.lang.ParserDefinition;
import com.intellij.lang.PsiParser;
import com.intellij.lexer.FlexAdapter;
import com.intellij.lexer.Lexer;
import com.intellij.openapi.project.Project;
import com.intellij.psi.tree.TokenSet;
import org.droneDSL.cli.parser.BotPsiParser;
import org.droneDSL.cli.parser._BotPsiLexer;
import org.jetbrains.annotations.NotNull;

public abstract class BotParserDefinitionBase implements ParserDefinition {
  @Override public @NotNull Lexer createLexer(Project project) {
    return new FlexAdapter(new _BotPsiLexer());
  }

  @Override public @NotNull PsiParser createParser(Project project) {
    return new BotPsiParser();
  }

  @Override public @NotNull TokenSet getCommentTokens() {
    return TokenSet.EMPTY;
  }

  @Override public @NotNull TokenSet getStringLiteralElements() {
    return TokenSet.EMPTY;
  }
}
