plugins { application }
application.mainClass.set("org.droneDSL.preprocess.Main")
dependencies {
    // Gson dependency
    implementation ("com.google.code.gson:gson:2.8.9")
}
// Configure the 'run' task to accept input from the console
tasks.named<JavaExec>("run") {
    standardInput = System.`in`
}


