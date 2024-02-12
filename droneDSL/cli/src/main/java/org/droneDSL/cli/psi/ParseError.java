package org.droneDSL.cli.psi;

import org.aya.pretty.doc.Doc;
import org.aya.util.error.SourcePos;
import org.aya.util.prettier.PrettierOptions;
import org.aya.util.reporter.Problem;
import org.jetbrains.annotations.NotNull;

public record ParseError(@Override @NotNull SourcePos sourcePos, @NotNull String message) implements Problem {
  @Override public @NotNull Doc describe(@NotNull PrettierOptions options) {
    return Doc.english(message);
  }

  @Override public @NotNull Problem.Severity level() {
    return Severity.ERROR;
  }
}
