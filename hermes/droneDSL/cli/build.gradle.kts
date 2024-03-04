plugins { application }
application.mainClass.set("org.droneDSL.cli.Main")

dependencies {
  api(libs.picocli)
  implementation(libs.aya.tools)
  implementation(libs.aya.ipcore)
  implementation(libs.aya.ipwrapper)
  implementation(project(":preprocess"))
  // Gson dependency
  implementation ("com.google.code.gson:gson:2.10.1")
}

val genDir = file("src/main/gen")
sourceSets["main"].java.srcDir(genDir)
idea.module {
  sourceDirs.add(genDir)
}

val lexer = tasks.register<JFlexTask>("lexer") {
  outputDir = genDir.resolve("org/droneDSL/cli/parser")
  jflex = file("src/main/grammar/BotPsiLexer.flex")
}

val genVer = tasks.register<GenerateVersionTask>("genVer") {
  basePackage = "org.droneDSL.cli"
  outputDir = genDir.resolve("org/droneDSL/cli/prelude")
}
listOf(tasks.sourcesJar, tasks.compileJava).forEach { it.configure { dependsOn(genVer, lexer) } }
