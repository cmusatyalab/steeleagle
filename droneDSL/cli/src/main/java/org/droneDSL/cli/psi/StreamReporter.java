package org.droneDSL.cli.psi;

import org.aya.util.reporter.Problem;
import org.aya.util.reporter.Reporter;
import org.jetbrains.annotations.NotNull;

import java.io.PrintStream;

public record StreamReporter(@NotNull PrintStream stream) implements Reporter {
  @Override public void report(@NotNull Problem problem) {
    stream.println(Reporter.errorMessage(problem, new DebugPrettierOptions(), true, false, 80));
  }
}