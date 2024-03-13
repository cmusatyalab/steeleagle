plugins { application }
val mainClassFQName = "org.droneDSL.compile.Main"
application.mainClass.set(mainClassFQName)
CommonTasks.fatJar(project, mainClassFQName)

dependencies {
  api(libs.picocli)
  implementation(libs.aya.tools)
  implementation(libs.aya.ipcore)
  implementation(libs.aya.ipwrapper)
  // Gson dependency
  implementation ("com.google.code.gson:gson:2.10.1")
}

val genDir = file("src/main/gen")
sourceSets["main"].java.srcDir(genDir)
idea.module {
  sourceDirs.add(genDir)
}

val lexer = tasks.register<JFlexTask>("lexer") {
  outputDir = genDir.resolve("org/droneDSL/compile/parser")
  jflex = file("src/main/grammar/BotPsiLexer.flex")
}

val genVer = tasks.register<GenerateVersionTask>("genVer") {
  basePackage = "org.droneDSL.compile"
  outputDir = genDir.resolve("org/droneDSL/compile/prelude")
}
tasks.compileJava.configure { dependsOn(genVer, lexer) }