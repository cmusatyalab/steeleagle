import org.aya.gradle.jflex.JFlexUtil
import org.gradle.api.DefaultTask
import org.gradle.api.tasks.InputFile
import org.gradle.api.tasks.OutputDirectory
import org.gradle.api.tasks.TaskAction

class JFlexTask extends DefaultTask implements Runnable {
  @OutputDirectory File outputDir
  @InputFile File jflex

  @TaskAction void run() {
    JFlexUtil.invokeJflex(outputDir, jflex, project.rootDir)
  }
}
