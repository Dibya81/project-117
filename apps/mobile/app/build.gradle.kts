import java.util.Properties

/*
 * Project 117 — Field Operations (Android app module).
 *
 * Dependency list is derived from what the source actually imports; libraries
 * present in the handoff's version catalog but never referenced are deliberately
 * NOT declared here (accompanist-permissions and datastore-preferences are the
 * two that are unused).
 *
 * The backend URLs are BuildConfig fields so a build can be pointed at a LAN
 * host or a production host without editing source — see SessionManager, which
 * resolves them per AppMode.
 */
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

/*
 * apps/mobile/local.properties is gitignored and is the natural place for a
 * machine-local backend URL, but the Android plugin only reads `sdk.dir` from it
 * — arbitrary keys are NOT exposed as Gradle properties. Load it explicitly so
 * the documented override works without touching a tracked file.
 *
 * `Properties` must be imported rather than written as `java.util.Properties`:
 * inside a Gradle Kotlin script `java` resolves to the Java plugin's extension,
 * which shadows the `java` package and makes `java.util` an unresolved reference.
 */
val localProperties = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

android {
    namespace = "com.project117.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.project117.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }

        /*
         * Backend environments.
         *
         * `P117_LOCAL_BACKEND_URL` is the only one that should ever be overridden
         * for day-to-day work. Pass it on the command line for your own network —
         * nothing in the repository hardcodes a machine's IP:
         *
         *   ./gradlew assembleDebug \
         *     -PP117_LOCAL_BACKEND_URL=http://your-lan-ip:8000/api/v1/
         *
         * or put `P117_LOCAL_BACKEND_URL=http://your-lan-ip:8000/api/v1/` in
         * apps/mobile/local.properties (gitignored), or in your user-level
         * ~/.gradle/gradle.properties. Later sources win over `local.properties`.
         */
        buildConfigField(
            "String",
            "PRODUCTION_BACKEND_URL",
            "\"${
                project.findProperty("P117_PRODUCTION_BACKEND_URL") as String?
                    ?: localProperties.getProperty("P117_PRODUCTION_BACKEND_URL")
                    ?: "https://api.project117.com/api/v1/"
            }\"",
        )
        buildConfigField(
            "String",
            "LOCAL_BACKEND_URL",
            "\"${
                project.findProperty("P117_LOCAL_BACKEND_URL") as String?
                    ?: localProperties.getProperty("P117_LOCAL_BACKEND_URL")
                    ?: "http://10.0.2.2:8000/api/v1/"
            }\"",
        )
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            // A debug build is what gets sideloaded onto a field handset, so the
            // demo/offline banner and verbose logging stay on.
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "true")
            buildConfigField("String", "ENVIRONMENT", "\"DEMO\"")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Release builds are HTTPS-only; cleartext is refused by the network
            // security config, not merely discouraged.
            buildConfigField("boolean", "ALLOW_CLEARTEXT", "false")
            buildConfigField("String", "ENVIRONMENT", "\"PRODUCTION\"")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    buildFeatures {
        compose = true
        // Read by Project117Application for debug-only logging.
        buildConfig = true
    }

    packaging {
        resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            isReturnDefaultValues = true
        }
    }
}

dependencies {
    // --- core / lifecycle -------------------------------------------------
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    // --- compose ----------------------------------------------------------
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    debugImplementation(libs.androidx.ui.tooling)

    // --- navigation -------------------------------------------------------
    implementation(libs.navigation.compose)

    // --- dependency injection --------------------------------------------
    implementation(libs.hilt.android)
    ksp(libs.hilt.android.compiler)
    implementation(libs.hilt.navigation.compose)

    // --- persistence ------------------------------------------------------
    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)
    implementation(libs.security.crypto)

    // --- background sync --------------------------------------------------
    implementation(libs.work.runtime.ktx)
    implementation(libs.hilt.work)
    ksp(libs.hilt.compiler)

    // --- network ----------------------------------------------------------
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.moshi)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging.interceptor)
    implementation(libs.moshi)
    implementation(libs.moshi.kotlin)
    ksp(libs.moshi.kotlin.codegen)

    // --- camera / scanning ------------------------------------------------
    implementation(libs.camerax.core)
    implementation(libs.camerax.camera2)
    implementation(libs.camerax.lifecycle)
    implementation(libs.camerax.view)
    implementation(libs.mlkit.barcode.scanning)

    // --- ui utilities -----------------------------------------------------
    implementation(libs.coil.compose)
    implementation(libs.timber)
    implementation(libs.kotlinx.coroutines.android)

    // --- tests ------------------------------------------------------------
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.mockk)
    testImplementation(libs.turbine)
    testImplementation(libs.room.testing)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.test.manifest)
}
