package com.project117.mobile

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.project117.mobile.ui.navigation.Project117NavGraph
import com.project117.mobile.ui.theme.Project117Theme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        /*
         * Light system bars.
         *
         * The app surface is now near-white (#F6F8FB). The default edge-to-edge
         * call requests *light-content* system bars, i.e. white icons, which
         * disappear against the light page. `SystemBarStyle.light` asks for dark
         * icons instead. minSdk is 26, so dark navigation-bar icons are always
         * available; the dark scrim is only a fallback for the status bar on
         * platforms without `windowLightStatusBar`.
         *
         * This is belt-and-braces with `android:windowLightStatusBar` in
         * res/values/themes.xml: the XML style covers the window before the
         * first Compose frame, this covers the running activity.
         */
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(Color.TRANSPARENT, DARK_SCRIM),
            navigationBarStyle = SystemBarStyle.light(Color.TRANSPARENT, DARK_SCRIM)
        )

        setContent {
            Project117Theme {
                Project117NavGraph()
            }
        }
    }

    private companion object {
        /** Project-117 navy, used only where dark icons are unavailable. */
        const val DARK_SCRIM = 0xFF0F172A.toInt()
    }
}
