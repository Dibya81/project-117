/*
 * Project 117 — Field Operations (Android).
 *
 * Standalone Gradle build. The mobile app is intentionally NOT part of the pnpm
 * workspace and does not consume any Node package: it is a native Android client
 * that talks to the Project 117 API through the FieldBackend abstraction.
 */
pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Project117FieldOperations"
include(":app")
