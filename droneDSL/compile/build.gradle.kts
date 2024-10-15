plugins { application }
val mainClassFQName = "org.droneDSL.compile.Compiler"
application.mainClass.set(mainClassFQName)
//CommonTasks.fatJar(project, mainClassFQName)

dependencies {
  api(libs.picocli)
  implementation(libs.aya.tools)
  implementation(libs.aya.ipcore)
  implementation(libs.aya.ipwrapper)
  // Gson dependency
  implementation ("com.google.code.gson:gson:2.10.1")
  implementation("org.locationtech.jts:jts-core:1.18.2")
  implementation("org.apache.commons:commons-math3:3.6.1")
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

val jarDep = tasks.register<Jar>("jarDep") {
  group = "build"
  manifest.attributes["Main-Class"] = "${project.group}.compile.Compiler"
  duplicatesStrategy = DuplicatesStrategy.INCLUDE
  dependsOn(configurations.runtimeClasspath)
  from({ configurations.runtimeClasspath.get().filter { it.name.endsWith("jar") }.map { zipTree(it) } })
  from(sourceSets.main.get().output)
  archiveClassifier.set("full")
}

val copyJarDep = tasks.register<Copy>("copyJarDep") {
  val jarDep = jarDep.get()
  dependsOn(jarDep)
  from(jarDep.archiveFile.get().asFile)
  into(System.getProperty("user.dir"))
  outputs.upToDateWhen { false }
}

tasks.compileJava.configure { dependsOn(genVer, lexer) }