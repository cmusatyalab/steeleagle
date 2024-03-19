plugins {
  java
  groovy
}

repositories { mavenCentral() }

dependencies {
  api(libs.aya.build.util)
  api(libs.aya.build.jflex)
}
