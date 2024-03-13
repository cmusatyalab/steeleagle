package org.droneDSL.compile.psi;

import com.intellij.psi.DefaultPsiParser;
import com.intellij.psi.builder.FleetPsiBuilder;
import com.intellij.psi.tree.IFileElementType;
import org.aya.intellij.GenericNode;
import org.aya.intellij.MarkerNodeWrapper;
import org.aya.util.error.SourceFile;
import org.aya.util.reporter.Reporter;
import org.jetbrains.annotations.NotNull;

import java.nio.file.Path;

public record DslParserImpl(@NotNull Reporter reporter) {
  public @NotNull GenericNode<?> parseNode(@NotNull String code) {
    var parser = new DslFleetParser();
    return new MarkerNodeWrapper(code, parser.parse(code));
  }

  private static @NotNull SourceFile replSourceFile(@NotNull String text) {
    return new SourceFile("<stdin>", Path.of("stdin"), text);
  }

  private static class DslFleetParser extends DefaultPsiParser {
    public DslFleetParser() {
      super(new BotParserDefinition());
    }

    private static final class BotParserDefinition extends BotParserDefinitionBase {
      private final @NotNull IFileElementType FILE = new IFileElementType(BotLanguage.INSTANCE) {
        @Override public void parse(@NotNull FleetPsiBuilder<?> builder) {
        }
      };

      @Override public @NotNull IFileElementType getFileNodeType() {
        return FILE;
      }
    }
  }
}
